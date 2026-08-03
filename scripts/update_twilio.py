import os
import getpass

def main():
    print("--- Twilio Credential Updater ---")
    sid = getpass.getpass("Enter TWILIO_ACCOUNT_SID: ").strip()
    token = getpass.getpass("Enter TWILIO_AUTH_TOKEN: ").strip()
    
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    
    if not os.path.exists(env_path):
        print(f"Error: .env file not found at {env_path}")
        return
        
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    import re
    # Replace the empty values
    content = re.sub(r"TWILIO_ACCOUNT_SID=.*", f"TWILIO_ACCOUNT_SID={sid}", content)
    content = re.sub(r"TWILIO_AUTH_TOKEN=.*", f"TWILIO_AUTH_TOKEN={token}", content)
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("\nSaved successfully to your local .env file!")

if __name__ == "__main__":
    main()
