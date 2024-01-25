# OCR Challenge

This is Harsha's submission to the OCR Challenge. To get the desired text, I resized the image to 1584 x 1224, got cropped images containing the desired text, extracted text from the cropped images, reformated the text to fit the desired output, and saved the text into a json file.

When I save the image from the pdf, the width/height ratio of the image is 1.294. To accurately crop the desired parts of the images, I resize the image to a specific width and height of 1584,1224. If the ratio is not 1.294, an error is thrown. 

I am using Google Cloud Vision for this project.

First, download the necessary packages by excuting this command 

```
pip install -r requirements. txt 
```

To run the script, gcloud must be installed. Complete steps 1-5 in this tutorial: https://cloud.google.com/functions/docs/tutorials/ocr#functions-deploy-command-python

To initialize the Google Cloud Functions, create the Google Buckets, and Pub/Sub functions, run 

```
bash excute.sh "your gcloud project id" initializeGCloud
```

To extract the text values on an image, excute this image:

```
bash excute.sh "your gcloud project id" processPhoto "relative filePath of image"
```

After this command,the utilityprocessedimages bucket will have the cropped images, and the utilityresults bucket will have the json file with the reformatted text. 

I was able to crop the desired parts of the image accurately. However, the OCR did not return accurate values all the time. For example, the OCR returned // instead of 11. In the json file, I displayed the raw OCR values. Unfortunately, I did not have time to fix this. If I had more time, I would focus on other OCR techniques like fuzzy matching to accurately extract the data. Fuzzy matching would be useful here because the output is close to the expected output but not exact. I would use a distance metric like Levenshtein or Hamming Distance for fuzzy matching.