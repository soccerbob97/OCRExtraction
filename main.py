# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START functions_cloudevent_ocr]
import base64
import json
import os
import cv2
import numpy as np
from tempfile import NamedTemporaryFile

from cloudevents.http import CloudEvent

import functions_framework

from google.cloud import pubsub_v1
from google.cloud import storage
from google.cloud import translate_v2 as translate
from google.cloud import vision


vision_client = vision.ImageAnnotatorClient()
translate_client = translate.Client()
publisher = pubsub_v1.PublisherClient()
storage_client = storage.Client()

project_id = os.environ.get("GCP_PROJECT")

@functions_framework.cloud_event
def process_image(cloud_event: CloudEvent) -> None:
    """ Edits the image to prepare for text extractions

    Args:
        cloud_event (CloudEvent): object sent by google function describing cloud event 

    Raises:
        ValueError: Throws if cloud event type is different from expected
    """

    # Check that the received event is of the expected type, return error if not
    expected_type = "google.cloud.storage.object.v1.finalized"
    received_type = cloud_event["type"]
    if received_type != expected_type:
        raise ValueError(f"Expected {expected_type} but received {received_type}")

    # Extract the bucket and file names of the uploaded image for processing
    data = cloud_event.data
    bucket = data["bucket"]
    file_name = data["name"]
    print("file name ", file_name)
    image = resize_image(bucket, file_name)
    dest_bucket_name, cropped_file_names = get_cropped_sections(image, file_name)
    detect_text(dest_bucket_name, cropped_file_names, file_name)
    print(f"File {file_name} processed.")
            
def resize_image(bucket: str, file_name: str):
    """
        Resizes input image to the dimension of 1584x1224 and saves result to cloud
    Args:
        bucket (str): Google Cloud bucket where the image file is located
        file_name (str): Name of the image file
    Raises:
        ValueError: Throws error if width/height ratio is not equal to 1.294
    Returns:
        A Resized ndarray Image 
    """
    source_bucket = storage_client.get_bucket(bucket)
    source_blob = source_bucket.get_blob(file_name)
    image = np.asarray(bytearray(source_blob.download_as_string()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_UNCHANGED)
    height, width, _ = image.shape
    ratio = round(width / height, 3)
    if ratio != 1.294:
        raise ValueError(f"Width to Height ratio is not equal to 1.294, width: {width} height: {height} width/height: {ratio}")
    if width > 1584 and height > 1224:
        image = cv2.resize(image, (1584, 1224), interpolation=cv2.INTER_AREA)
    elif width < 1584 and height < 1224:
        image = cv2.resize(image, (1584, 1224), interpolation=cv2.INTER_LINEAR)
    # Creates the resized file and saves to cloud
    with NamedTemporaryFile() as temp:
        temp_file = "".join([str(temp.name), "og_image.jpg"])
        cv2.imwrite(temp_file, image)
        temp_blob = source_bucket.blob(file_name)
        temp_blob.upload_from_filename(temp_file)
    return image

def get_cropped_sections(image, file_name):
    """
    Saves cropped images that displays the desired values to the cloud.

    Args:
        image (ndarray): input image that needs to be cropped
        file_name (string): Name of the image file
    Returns:
        string: bucket where cropped images will be stored
        list[string]: list of cropped images names
    """
    # dimensions to crop images to, format: x,y,h,w
    cropped_dims = [(171, 405, 57, 111), (355, 125, 52, 351), (1050, 200, 125, 200), (111, 504, 43, 225)]
    cropped_file_names = ["renew_size", "nearest_crossed_street", "house_number", "renew_date"]
    dest_bucket_name = os.environ['PROCESSED_BUCKET']
    dest_bucket = storage_client.get_bucket(dest_bucket_name)
    for index in range(len(cropped_dims)):
        cropped_dim = cropped_dims[index]
        cropped_file_name = cropped_file_names[index] + "_" + file_name
        x,y,h,w = cropped_dim
        crop_image = image[y:y + h, x:x + w]
        with NamedTemporaryFile() as temp:
            temp_file = "".join([str(temp.name), cropped_file_name])
            cv2.imwrite(temp_file, crop_image)
            dest_blob = dest_bucket.blob(cropped_file_name)
            dest_blob.upload_from_filename(temp_file)
            print(f"File {cropped_file_names[index]} saved to {dest_bucket_name} bucket")
    return dest_bucket_name, cropped_file_names
    

def detect_text(bucket: str, cropped_file_names: list[str], file_name: str) -> None:
    """
    Detect text in all the cropped images and reformat text output to match format

    Args:
        bucket (str): bucket name where the cropped images are stored
        cropped_file_names (list[str]): list of cropped images names
        file_name (str): input image file name 
    """
    print(f"Looking for text in image {file_name}")

    # Use the Vision API to extract text from the image
    utility_map = {}
    original_map = {}
    for cropped_file_name in cropped_file_names:
        cropped_file_name_cloud = cropped_file_name + "_" + file_name
        # Get Text from cropped images
        image = vision.Image(
            source=vision.ImageSource(gcs_image_uri=f"gs://{bucket}/{cropped_file_name_cloud}")
        )
        text_detection_response = vision_client.text_detection(image=image)
        annotations = text_detection_response.text_annotations
        # Reformat Text output
        if annotations:
            text = annotations[0].description
            original_map[cropped_file_name] = text
            if cropped_file_name == "renew_size":
                text = text.replace("\"","")
                accept_set = {"1/2", "3/4", "1"}
                if text == "162":
                    text = "1/2"
                elif text == "364":
                    text = "3/4"
                if text not in accept_set:
                    text = ""
            elif cropped_file_name == "nearest_crossed_street":
                text = text.replace("\n"," ")
                if text.find(".") >= 0 and len(text.split(".")) > 1:
                    text = text.split(".")[1]
            elif cropped_file_name == "house_number":
                text = text.replace("\n"," ")
                text = text.split(" ")[-1]
            elif cropped_file_name == "renew_date":
                text = text.replace("\n"," ")
                text = text.split(" ")[-1]    
        else:
            text = ""    
        print(f"{cropped_file_name} text value: ", text)
        utility_map[cropped_file_name] = text
    utility_map["original_translation"] = original_map
    # Sending message to cloud service that saves data
    message = {
            "utility_map": utility_map,
            "filename": file_name
        }
    message_data = json.dumps(message).encode("utf-8")
    result_name = os.environ.get("RESULT_NAME")
    result_path = publisher.topic_path(project_id, result_name)
    future = publisher.publish(result_path, data=message_data)
    future.result()

@functions_framework.cloud_event
def save_result(cloud_event: CloudEvent) -> None:
    """
    Saves extracted text to the cloud.

    Args:
        cloud_event (CloudEvent): object sent by google function describing cloud event 

    Raises:
        ValueError: Throws if cloud event type is different from expected
        ValueError: Throws if message cannot be decoded
    """
    
    # Check that the received event is of the expected type, return error if not
    expected_type = "google.cloud.pubsub.topic.v1.messagePublished"
    received_type = cloud_event["type"]
    if received_type != expected_type:
        raise ValueError(f"Expected {expected_type} but received {received_type}")

    # Extract the message body, expected to be a JSON representation of a
    # dictionary, and extract the fields from that dictionary.
    data = cloud_event.data["message"]["data"]
    try:
        message_data = base64.b64decode(data)
        message = json.loads(message_data)
        utility_map = message["utility_map"]
        filename = message["filename"]
        print(f"filename {filename}")
    except Exception as e:
        raise ValueError(f"Missing or malformed PubSub message {data}: {e}.")

    print(f"Received request to save file {filename}.")
    
    utility_json = json.dumps(utility_map, indent=4)
    
    # Save extracted text to a json file
    with open("content.json", "w") as outfile:
        outfile.write(utility_json)

    bucket_name = os.environ["RESULT_BUCKET"]
    filename_no_ext = filename.split(".")[0]
    result_filename = f"{filename_no_ext}.json"
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(result_filename)
    print(f"Saving result to {result_filename} in bucket {bucket_name}.")
    blob.upload_from_filename("content.json")
    print("File saved.")