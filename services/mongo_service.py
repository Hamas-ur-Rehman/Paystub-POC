import os
import time
from dotenv import load_dotenv
from .logger import log
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
load_dotenv()

class MongoDBService:
    def insert_chat(self,**kwargs):
        try:
            start_time = time.time()
            con=os.getenv("MONGODB")
            kwargs["created_at"]=datetime.now()
            with MongoClient(con) as client:
                client["paystub"]["chats"].insert_one(kwargs)
            log.info(f"Time taken for insert_chat: {round(time.time() - start_time,2)}")
        except Exception as e:
            log.error(f"Error in insert_chat: {e}", exc_info=True)
            return "Sorry, I am unable to process your request at the moment. Please try again later."


    def fetch_chats(self,session_id:str):
        try:
            history = []
            complete_history = []
            start_time = time.time()
            con=os.getenv("MONGODB")
            with MongoClient(con) as client:
                chats = list(
                    client["paystub"]["chats"]
                    .find({"session_id": session_id})
                    .sort("created_at", ASCENDING)
                    # .limit(6)
                )
                log.info(f"Time taken for fetch_chats: {round(time.time() - start_time, 2)} seconds")
                history = [chat.get("history") for chat in chats]
                for i in history:
                    complete_history.extend(i)
                log.info(f"Time taken for fetch_chats: {round(time.time() - start_time,2)}")

                return complete_history
        except Exception as e:
            log.error(f"Error in fetch_chats: {e}", exc_info=True)
            return "Sorry, I am unable to process your request at the moment. Please try again later."
        