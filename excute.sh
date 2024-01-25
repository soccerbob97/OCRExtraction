#!/bin/bash

createBuckets() {
    gsutil mb gs://utilityimages
    gsutil mb gs://utilityprocessedimages
    gsutil mb gs://utilityresults
    gcloud pubsub topics create UtilityResults
}

processImage() {
   echo "in process" 
   gcloud functions deploy ocr-extract \
        --gen2 \
        --runtime=python312 \
        --region=us-east1 \
        --source=. \
        --entry-point=process_image \
        --trigger-bucket utilityimages \
        --trigger-location=us \
        --set-env-vars "^:^GCP_PROJECT=utilityocr-411814:RESIZE_NAME=UtilityResize:PROCESSED_BUCKET=utilityprocessedimages:RESULT_NAME=UtilityResults"
}

saveResult() {
    echo "in save" 
    gcloud functions deploy ocr-save2 \
        --gen2 \
        --runtime=python311 \
        --region=us-east1 \
        --source=. \
        --entry-point=save_result \
        --trigger-topic UtilityResults \
        --set-env-vars "GCP_PROJECT=utilityocr-411814,RESULT_BUCKET=utilityresults"
}

processName=$1
if [ "$processName" = "initializeGCloud" ]; then
    createBuckets
    processImage
    saveResult
elif [ "$processName" = "processPhoto" ]; then
    fileName=$2
    if [[ -f "$fileName" ]]; then
        gsutil cp $fileName gs://utilityimages  
    else
        echo 'File does not exist.'
    fi
elif [ "$processName" = "compileCloudFunctions" ]; then
    echo "in all"
    processImage
    saveResult
else
    echo "$processName"
    echo "Option Not Found: choose processImage, saveResult, resizeImage or all"
fi




