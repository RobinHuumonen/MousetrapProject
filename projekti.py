import projekti_hiirenTunnistusKuvasta
import mysql.connector
import RPi.GPIO as GPIO
import time
import requests
from picamera import PiCamera
from twilio.rest import Client

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

#set GPIO Pins
TRIGGER = 18
ECHO = 23
TRIGGER2 = 2
ECHO2 = 3
servo2 = 27
servo = 17

#set GPIO direction (IN / OUT)
GPIO.setup(TRIGGER, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.setup(TRIGGER2, GPIO.OUT)
GPIO.setup(ECHO2, GPIO.IN)
GPIO.setup(servo, GPIO.OUT)
GPIO.setup(servo2, GPIO.OUT)

pwm=GPIO.PWM(servo, 50)
pwm.start(0)
pwm2=GPIO.PWM(servo2, 50)
pwm2.start(0)

def sendSMS():
    account_sid = ''
    auth_token = ''
    my_number = ''
    twilio_number = ''
    client = Client(account_sid,auth_token)
    message = client.messages.create(
                body = 'Hiiri sailio taysi!',
                from_=twilio_number,
                to=my_number
                )
    return message

def takePhoto():
    timestr = time.strftime("%Y%m%d-%H%M%S")
    imageFileName = "img-"+timestr+".jpg"
    # PiCamv2 initialization  
    camera = PiCamera()
    camera.resolution = (720, 480)
    # capture image
    camera.capture('/home/pi/tensorflow1/models/research/object_detection/kuvat/%s' % imageFileName)
    time.sleep(1)
    camera.close()
    return imageFileName
    
def sendPhotoToWeb(imgName):
    url = "http://stulinux53.ipt.oamk.fi/codeigniter/application/models/photoUpload.php/"
    # send file to server
    files = {'file': open('/home/pi/tensorflow1/models/research/object_detection/kuvat/%s' % imgName, 'rb')}
    rq = requests.post(url,files=files)
    # Wait for 10 milliseconds
    time.sleep(0.01)
    messageBack = "Viimeksi web-palvelimelle lahetetty kuva: " + imgName
    return messageBack

def movementDetector():
    movementDetected = 0
    # set Trigger to HIGH
    GPIO.output(TRIGGER2, True)
    # set Trigger after 0.01ms to LOW
    time.sleep(0.00001)
    GPIO.output(TRIGGER2, False)
    startTime = time.time()
    stopTime = time.time()
    # save StartTime
    while GPIO.input(ECHO2) == 0:
        startTime = time.time()
    # save time of arrival
    while GPIO.input(ECHO2) == 1:
        stopTime = time.time()
    # time difference between start and arrival
    timeElapsed = stopTime - startTime
    # multiply with the sonic speed (34300 cm/s)
    # and divide by 2, because there and back
    distance = (timeElapsed * 34300) / 2
    time.sleep(0.2)
    if (distance > 14 or distance < 8):
        movementDetected = 1
    else:
        movementDetected = 0
        
    return movementDetected

def checkFillFactor():
    # set Trigger to HIGH
    GPIO.output(TRIGGER, True)
    # set Trigger after 0.01ms to LOW
    time.sleep(0.00001)
    GPIO.output(TRIGGER, False)
    startTime = time.time()
    stopTime = time.time()
    # save StartTime
    while GPIO.input(ECHO) == 0:
        startTime = time.time()
    # save time of arrival
    while GPIO.input(ECHO) == 1:
        stopTime = time.time()
    # time difference between start and arrival
    timeElapsed = stopTime - startTime
    # multiply with the sonic speed (34300 cm/s)
    # and divide by 2, because there and back
    distance = (timeElapsed * 34300) / 2
    #print ("Measured Distance = %.1f cm" % distance)
    time.sleep(1)
    #print("fillfaktori etaisyys", distance)
    fillFactor = 0
    if (distance <= 4):
        fillFactor = 100
    elif (distance <= 8):
        fillFactor = 75
    elif (distance <= 11):
        fillFactor = 50
    elif (distance <= 14):
        fillFactor = 25
    elif (distance >= 13):
        fillFactor = 0

    return fillFactor

def setFrontHatchAngle(angle):
    duty = angle / 20 + 2
    GPIO.output(servo, True)
    pwm.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(servo, False)
    pwm.ChangeDutyCycle(0)
    
def setBottomHatchAngle(angle):
    duty = angle / 20 + 2
    GPIO.output(servo2, True)
    pwm2.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(servo2, False)
    pwm2.ChangeDutyCycle(0)
        
mouses = 0
fillFactor = 0
idkaappaus = None
setBottomHatchAngle(155)
setFrontHatchAngle(65)

while(1):
    if movementDetector():
        # Close hatch
        setFrontHatchAngle(140)
        # Take picture with timestamp as filename and return filename to image-variable
        image = takePhoto()
        # Send picture's filename taken above to detection-script using tensorflow-model
        mouseDetected = projekti_hiirenTunnistusKuvasta.mouseDetectorFromPicture(image)
        print("tunnistus arvo: ",mouseDetected)
        if (mouseDetected >= 0.6):
          # Open and close bottom hatch
            setBottomHatchAngle(7)
            setBottomHatchAngle(155)
            print('hiiret++')
            # Send photo of the captured thing to web
            print(sendPhotoToWeb(image))

            # Open mysql-connection
            mydb = mysql.connector.connect(host="stulinux53.ipt.oamk.fi",user="ryhma3",passwd="meolemmeryhma3",database="codeigniter") 
            mycursor = mydb.cursor()
 
          # Update mouse container's fill factor procentage via ultrasonic sensor
            fillFactor = checkFillFactor()
            print("fillfaktori: ", fillFactor)
  
            sql = "INSERT INTO hiiri VALUES (%s, %s)"
            val = (idkaappaus, fillFactor)
            
            try:
                # Execute the SQL command
                mycursor.execute(sql, val)
                # Commit changes in database
                mydb.commit()
            except mysql.connector.Error as err:
                print("Virhe: {}".format(err))
                
            # Diconnect from the server    
            mydb.close()
            
            # If mouse container is full notify via SMS and terminate script
          if (fillFactor == 100):
                print(sendSMS())
                exit()
                
            # Open front hatch for a new entrapment
            setFrontHatchAngle(65)
            
        else:
            # If mouse wasn't detected, let wrongfully captured thing out
            setFrontHatchAngle(65)
            print('else')
            