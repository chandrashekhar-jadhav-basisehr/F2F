# Standard library imports
import io
import json
import os
import threading
import time
import uuid
from datetime import datetime
from queue import Queue

# Third-party imports
import requests
import torch
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from paddleocr import PaddleOCR
from torchvision.transforms.functional import InterpolationMode

# Local application imports
from helpers.downloadpdf import download_file
from helpers.generate_images import generate_images
from helpers.load_model import load_model
from helpers.timeutils import TimeManager, MAX_PROCESSING_TIME
from scripts.classify_documents import classify_pdf
from scripts.main import main, upload_status

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
RESULT_FOLDER = os.path.join(BASE_DIR, "results")

# Ensure the directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

qwen_model, qwen_processor, pipeline= load_model()

processing_status = {}
task_queue = Queue()
processing_lock = threading.Lock()
worker_thread = None

def process_queue():
    while True:
        try:
            st=time.time()
            # Get the next task from queue
            file_uuid = task_queue.get()
            if file_uuid is None:  # Poison pill to stop the thread
                break

            with processing_lock:
                save_path = os.path.join(UPLOAD_FOLDER, f'{file_uuid}.pdf')
               
                # IF DOC TYPE == FACESHEET ADD TO QUEUE DIRECTLY
                doc_type = processing_status[file_uuid].get("doc_type")
                if doc_type and doc_type.lower() not in ["f2f","f2f notes","facesheet", "facesheets","poc","POC"]:
                    print("NOT FACESHEET or F2F IN DOCURL...")
                    processing_status[file_uuid]["status"]="failed"
                    upload_status(file_uuid,processing_status,"PDF is not a facesheet or f2f or POC")
                    continue

                # ELSE DO CLASSIFICATION
                else:
                    processing_status[file_uuid]['status'] = "Classification"
                    upload_status(file_uuid,processing_status,"Classifying document")
                   
                    facesheet_count, f2f_count, poc_count, document_metadata = classify_pdf(save_path, file_uuid, processing_status)

                    print("Facesheet count",facesheet_count)
                    print("F2F count",f2f_count)
                    print("POC count",poc_count)
                    processing_status[file_uuid]["documents"]= document_metadata
                    
                    if f2f_count > 0:
                        processing_status[file_uuid]["f2f"]= True

                    if poc_count > 0:
                        processing_status[file_uuid]["poc"]= True
                        
                    # IF FACESHEET ADD TO QUEUE
                    if facesheet_count > 0:
                        processing_status[file_uuid]["facesheet"]= True
                    # ELSE RETURN FILE NOT FACESHEET
                    if facesheet_count == 0 and f2f_count == 0 and poc_count == 0:
                        processing_status[file_uuid]["status"]= "failed"
                        upload_status(file_uuid,processing_status,"File is not a facesheet or F2F or POC")
                        continue
                try:
                    processing_status[file_uuid]["status"] = "processing"
                    TimeManager.get_instance().mark_task_started(file_uuid)

                    # Create a thread for the task with a timeout
                    task_thread = threading.Thread(target=main, args=(file_uuid,qwen_model,qwen_processor,pipeline,processing_status,))
                    task_thread.start()
                    task_thread.join(timeout=MAX_PROCESSING_TIME)
                    if task_thread.is_alive():
                        # Task exceeded timeout
                        processing_status[file_uuid]["status"] = "failed".format(MAX_PROCESSING_TIME)
                        # Upload Status
                        upload_status(file_uuid,processing_status,"Timeout")

                    else:
                        TimeManager.get_instance().mark_task_completed(file_uuid)

                except Exception as e:
                    processing_status[file_uuid]["status"] = f"failed"
                    TimeManager.get_instance().mark_task_completed(file_uuid)
                    upload_status(file_uuid,processing_status,f"Error: {str(e)}")

                finally:
                    nd=time.time()-st
                    print("Total time",nd)
                    task_queue.task_done()
        except Exception as e:
            upload_status(id,processing_status,f"Error in queue processing: {str(e)}")
            print(f"Error in queue processing: {str(e)}")

def ensure_worker_thread():
    global worker_thread
    if worker_thread is None or not worker_thread.is_alive():
        worker_thread = threading.Thread(target=process_queue, daemon=True)
        worker_thread.start()

@app.route('/result/<string:file_uuid>', methods=['GET'])
def get_json(file_uuid):
    # Check if the result file exists in the results directory
    result_path = os.path.join(RESULT_FOLDER, f'{file_uuid}.json')
    if os.path.exists(result_path):
        with open(result_path, 'r') as f:
            result = f.read()
        return result
    else:
        return jsonify({'error': 'Result not found'}), 404

@app.route('/status/<string:file_uuid>', methods=['GET'])
def get_status(file_uuid):
    status = processing_status.get(file_uuid, "not_found")
    result_path = os.path.join(RESULT_FOLDER, f'{file_uuid}.json')

    response = {
        'status': status,
        'id': file_uuid,
        'timing_info': TimeManager.get_instance().get_task_times(file_uuid)
    }

    # Include queue position if status is queued
    if status == "queued":
        items = list(task_queue.queue)
        try:
            position = items.index(file_uuid) + 1
            response['queue_position'] = position
        except ValueError:
            response['queue_position'] = 0

    # Return result if status contains "completed"
    if isinstance(status, str) and "completed" in status.lower():
        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                response['result'] = json.load(f)
        else:
            response['result'] = "Result file not found despite completed status"

    return jsonify(response)

@app.route('/upload', methods=['POST'])
def fetch_documents():
    try:
        data = request.get_json()
        user_id= data.get('id')
        result_path = os.path.join(RESULT_FOLDER, f'{user_id}.json')

        if os.path.exists(result_path):
            os.remove(result_path)

        documents=data.get('documents',[])
        for doc in documents:
            doc_url = doc.get('doc_url')
            doc_type = doc.get('doc_type') 
            file_name = os.path.basename(doc_url)
            processing_status[user_id] = {}
            processing_status[user_id]["ocr"]=""
                
            if not doc_url.lower().endswith('.pdf'):
                return {"error": "Unsupported format"}
            if doc_type:
                processing_status[user_id]["doc_type"]= doc_type 
                
            save_path = os.path.join(UPLOAD_FOLDER, f'{user_id}.pdf')
            download_file(doc_url, save_path)
            processing_status[user_id]["status"]= "queued" 
            task_queue.put(user_id)
            ensure_worker_thread()
            
        return {"message": "file uploaded successfully"}
    except Exception as e:
        return {"message":str(e)}

@app.route('/queue/status', methods=['POST'])
def get_queue_status():
    data = request.get_json()
    print(data)
    return data

if __name__ == '__main__':
    app.run(host='0.0.0.0')
