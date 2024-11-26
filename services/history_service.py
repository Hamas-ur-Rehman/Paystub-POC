import json
import os


class HistoryService:
    def __init__(self):
        self.file_path = "history.json"

    def insert_chat(self, session_id: str, history: dict):
        file_path = self.file_path

        # Check if the file exists, if not create it with an empty dictionary
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                json.dump({}, file)
        
        # Load existing data from the file
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Check if the session ID already exists
        if session_id in data:
            # Append the new history to the existing history list
            if isinstance(data[session_id], list):
                data[session_id].extend(history)
            else:
                data[session_id] = [data[session_id], history]
        else:
            # Add a new session with the history
            data[session_id] = history
        
        # Save updated data back to the file
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)



    def fetch_chats(self, session_id: str):
        file_path = self.file_path
        # Check if the file exists
        if not os.path.exists(file_path):
            return []  # Return empty list if the file doesn't exist

        # Load existing data from the file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Return the history for the session ID, or an empty list if it doesn't exist
        return data.get(session_id, [])