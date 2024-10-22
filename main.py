from fastapi import FastAPI, Request, Form, Cookie, Response
from twilio.rest import Client
from decouple import config
import requests
from requests.auth import HTTPBasicAuth
import mimetypes
from gradio_client import Client as gradioClient
from gradio_client import file
import urllib.parse
from contextlib import asynccontextmanager
from db import init_db, update_image, get_images

import cloudinary
import cloudinary.uploader

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    init_db()
    yield
    print("app shutdown")

app = FastAPI(lifespan=lifespan)

# Twilio credentials from environment variables
account_sid = config("TWILIO_ACCOUNT_SID")
auth_token = config("TWILIO_AUTH_TOKEN")
twilio_number = config('TWILIO_NUMBER')
my_number=config("MY_NUMBER")
client = Client(account_sid, auth_token)

# Configuration       
cloudinary.config( 
    cloud_name = "daroksk6d",
    api_key = config( "CLOUDINARY_API_KEY"), 
    api_secret = config( "CLOUDINARY_SECRET"), # Click 'View API Keys' above to copy your API secret
    secure=True
)

# Global variables to store the conversation state
last_image_url = None
filename = None
first_image_done = 0



@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
                        From: str=Form(None), 
                        Body: str=Form(...),
                        NumMedia: int=Form(0), 
                        MediaUrl0: str=Form(None)
                    ):
    """Endpoint for receiving incoming messages from WhatsApp."""
    
    global last_image_url, first_image_done, filename

    print(f"Received payload: {Body},{NumMedia},{MediaUrl0}")
    sender = From
    message_body = Body.strip().lower()
    num_media = int(NumMedia)

    response_message = "You said: " + message_body
    print(message_body)

    # Check if an image is attached
    if num_media > 0 and MediaUrl0:
        last_image_url = MediaUrl0  # Store the URL of the last received image

        # Attempt to download the media
        response = requests.get(last_image_url, auth=HTTPBasicAuth(account_sid, auth_token)) 
        
        if response.status_code == 200:
            # Determine the media's content type and its extension
            content_type = response.headers.get('Content-Type')
            extension = mimetypes.guess_extension(content_type)
            
            # Define the filename dynamically based on the content type
            filename = f"downloaded_media_{first_image_done}{extension}"

            # Save the media file
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Media downloaded successfully as {filename}")
            
            # Prompt user to specify if the image is of a person or garment
            response_message = "Is this image of a person (P) or a garment (G)?"

        else:
            print(f"Failed to download media. Status code: {response.status_code}")
            response_message = f"Failed to download media from {last_image_url}."
    
   # Handle user responses for specifying image type
    else:
        # Retrieve stored image data for the sender
        images = get_images(sender)

        if images is None:
            if message_body in ['p', 'person']:
                update_image(sender, 'person', filename)  # Store person image
                first_image_done =1
                response_message = "Person image uploaded successfully! Now, upload the garment image."

            elif message_body in ['g', 'garment']:
                update_image(sender, 'garment', filename)  # Store garment image
                first_image_done =1
                response_message = "Garment image uploaded successfully! Now, upload the person image."
            else:
                person_image, garment_image = None, None
                response_message = "Please upload both the person and garment images."
                # Sending response back to WhatsApp
            send_message(client, response_message)
            return {"status":"Message Received"}
          # No records found for the sender
        person_image, garment_image = images  # Unpack the retrieved images

        if person_image or garment_image:

            if garment_image and message_body in ['p', 'person']:
                update_image(sender, 'person', filename)  # Store person image
                person_image = filename
                response_message = "Person image uploaded successfully! Now, upload the garment image."

            elif person_image and message_body in ['g', 'garment']:
                update_image(sender, 'garment', filename)  # Store garment image
                garment_image = filename
                response_message = "Garment image uploaded successfully! Now, upload the person image."

            response_message = "Both person and garment images have been uploaded successfully."

            result = get_tryon_image(person_image, garment_image)

            print(result)
            
            update_image(sender, 'person', None)
            update_image(sender, 'garment', None)
            
            with open(result, "rb") as img_file:
                image_data = img_file.read()

            
            with open("result.jpg", "wb") as f:
                f.write(image_data)

            upload_result = cloudinary.uploader.upload("result.jpg")

            final_image_url = upload_result['secure_url']

            # Send the final image to the user
            client.messages.create(
                media_url=[final_image_url],
                from_=twilio_number,
                to=my_number
            )

        
        else:
            response_message = "Invalid response. Please specify if the image is of a person (P) or a garment (G)."


    # Sending response back to WhatsApp
    send_message(client, response_message)

    return {"status": "Message received"}

@app.post("/send-image")
async def send_image(to: str, image_url: str):
    """Endpoint for sending an image to a specific WhatsApp number."""
    message = client.messages.create(
        media_url=[image_url],
        from_=twilio_number,
        to=to
    )
    return {"status": "Image sent", "message_sid": message.sid}

def get_tryon_image(person_image, garment_image):

    gradioclient = gradioClient("Nymbo/Virtual-Try-On")
    result = gradioclient.predict(
		dict={"background":file(person_image),"layers":[],"composite":None},
		garm_img=file(garment_image),
		garment_des="Hello!!",
		is_checked=True,
		is_checked_crop=False,
		denoise_steps=30,
		seed=42,
		api_name="/tryon"
    )

    return result[0]

def send_message(client, response_message):
    client.messages.create(
        from_=f"whatsapp:{twilio_number}",
        body=response_message,
        to=f"whatsapp:{my_number}",
    )
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
