# SingleAPI Project

## Overview
SingleAPI is a Flask-based application designed to process medical documents, extract relevant information using the Qwen model, and classify document types. The application supports downloading documents from URLs, processing them, and providing status updates and results.

## Setup

### Prerequisites
- Python 3.10
- pip (Python package installer)

### Installation
1. Clone the repository:
    ```sh
    git clone https://git.digiquanta.com/monad/singleapi
    cd singleapi
    ```

2. Run the setup script: (Dont run this step until you are on GPU!)
This is for installation of models
    ```sh
    ./run.sh
    ```

## Usage

### Running the Application
To start the Flask application, run:
```sh
python app.py
```

The application will be available at `http://0.0.0.0:5000`.

### API Endpoints

#### Upload Document
- **URL:** `/upload`
- **Method:** `POST`
- **Description:** Uploads a document for processing.
- **Request Body:**
    ```json
    {
        "id": "unique_user_id",
        "documents": [
            {
                "doc_url": "http://example.com/document.pdf",
                "doc_type": "facesheet" (optional)
            }
        ]
    }
    ```
- **Response:**
    ```json
    {
        "message": "file uploaded successfully"
    }
    ```

