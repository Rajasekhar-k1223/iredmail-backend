from flask import Flask, request, jsonify
import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

app = Flask(__name__)

# Secret key for JWT (ensure this is a strong secret key)
app.config['JWT_SECRET_KEY'] = 'your_secret_key_here'
jwt = JWTManager(app)

# Dummy user store for demonstration (you should use a database in production)
USERS = {
    'user@example.com': {
        'password': 'password123'
    }
}

# Helper function to authenticate user and generate JWT token
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    # Verify user credentials
    if email in USERS and USERS[email]['password'] == password:
        # Create JWT access token
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401

# Helper function to connect to the IMAP server (for receiving emails)
def connect_to_imap(username, password, imap_server="localhost"):
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(username, password)
        return mail
    except Exception as e:
        return None

# Helper function to list received emails from the inbox
def list_inbox_emails(mail, folder="INBOX", limit=10):
    try:
        mail.select(folder)
        status, email_ids = mail.search(None, "ALL")
        email_ids = email_ids[0].split()
        emails = []

        for email_id in email_ids[-limit:]:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    from_ = msg.get("From")
                    emails.append({"subject": subject, "from": from_})

        return emails
    except Exception as e:
        return []

# Helper function to send an email using SMTP
def send_email(sender, recipient, subject, body, smtp_server="localhost", smtp_port=587, smtp_username=None, smtp_password=None):
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Use TLS for security
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        return True
    except Exception as e:
        return False, str(e)

# API to send emails (JWT-protected)
@app.route('/send-mail', methods=['POST'])
@jwt_required()
def send_mail():
    try:
        data = request.json
        domain = data.get('domain')
        username = data.get('username')
        password = data.get('password')
        recipient = data.get('recipient')
        subject = data.get('subject')
        body = data.get('body')

        if not all([domain, username, password, recipient, subject, body]):
            return jsonify({"error": "Missing required fields"}), 400

        # Construct sender email address and smtp server based on domain
        sender = f"{username}@{domain}"
        smtp_server = "localhost"  # Change this if you're not sending mail from localhost

        # Send the email
        success, error_message = send_email(sender, recipient, subject, body, smtp_server=smtp_server, smtp_username=sender, smtp_password=password)

        if success:
            return jsonify({"message": "Email sent successfully!"}), 200
        else:
            return jsonify({"error": error_message}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API to fetch inbox emails (JWT-protected)
@app.route('/get-mails', methods=['POST'])
@jwt_required()
def get_mails():
    try:
        data = request.json
        domain = data.get('domain')
        username = data.get('username')
        password = data.get('password')

        if not all([domain, username, password]):
            return jsonify({"error": "Missing domain, username, or password"}), 400

        email_address = f"{username}@{domain}"
        imap_server = "localhost"  # Update this if your IMAP server is hosted elsewhere

        # Connect to the iRedMail IMAP server
        mail = connect_to_imap(email_address, password, imap_server)
        if not mail:
            return jsonify({"error": "Failed to connect to the email server"}), 500

        # Fetch emails from INBOX
        emails = list_inbox_emails(mail)

        # Logout from the mail server
        mail.logout()

        return jsonify({"emails": emails}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
