import cv2
image = cv2.imread("images/new-image.jpg")
#print("image ", image)
x,y,h,w = 111, 504, 43, 225
crop_image = image[y:y + h, x:x + w]
#print("crop ", crop_image)
cv2.imwrite("test.jpg", crop_image)