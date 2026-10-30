import os
import resend

class EmailService:
    def __init__(self):
        # resend python SDK uses the resend.api_key attribute
        resend.api_key = os.environ.get("RESEND_API_KEY")
        self.to_email = os.environ.get("RESEND_TO_EMAIL", "your_email@example.com")

    def send_intrusion_email(self, reason: str, image_url: str):
        if not resend.api_key:
            print("RESEND_API_KEY not set. Cannot send email.")
            return

        print(f"Sending intrusion email to {self.to_email}...")
        
        try:
            params = {
                "from": "onboarding@resend.dev",
                "to": [self.to_email],
                "subject": "Intrusion Alert!",
                "html": f"<h2>Intrusion Detected</h2><p><strong>Reason:</strong> {reason}</p><p><img src='{image_url}' alt='Intrusion Image' width='400'/></p>",
            }
            email = resend.Emails.send(params)
            print(f"Email sent successfully: {email}")
        except Exception as e:
            print(f"Failed to send email: {e}")

email_service = EmailService()
