from flask import Flask, request, jsonify
import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo
from ldap3 import Server, Connection, ALL

# Flask app and configuration
app = Flask(__name__)

# Secret key for JWT
app.config['JWT_SECRET_KEY'] = 'jbbkhvhgHGCUYHTCBUY681791htctrcygybtcy'

# SQLAlchemy configuration for MySQL or PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Admin@1223@localhost/vmail'
db = SQLAlchemy(app)

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/emails_db"
mongo = PyMongo(app)

# JWT Manager
jwt = JWTManager(app)

# LDAP configuration (connecting to iRedMail's LDAP server)
LDAP_SERVER = "ldap://localhost"
LDAP_USER_DN = "cn=admin,dc=example,dc=com"  # Change this to your LDAP admin user DN
LDAP_PASSWORD = "Admin@123"


### SQLAlchemy Models for SQL Database ###
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)


class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())


### Helper Functions for LDAP ###
def authenticate_ldap_user(email, password):
    server = Server(LDAP_SERVER, get_info=ALL)
    conn = Connection(server, LDAP_USER_DN, LDAP_PASSWORD, auto_bind=True)

    # Search for the user in the LDAP directory
    search_filter = f"(mail={email})"
    conn.search('dc=example,dc=com', search_filter, attributes=['cn', 'mail'])
    
    if conn.entries:
        return True
    return False


### Helper Function to Log Email to MongoDB ###
def log_email_to_mongo(sender, recipient, subject, body):
    email_log = {
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "timestamp": db.func.now()
    }
    mongo.db.email_logs.insert_one(email_log)


### API Endpoints ###

# User login and JWT token generation using LDAP authentication
# User login and JWT token generation with fallback to SQL
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    # Attempt LDAP authentication
    if authenticate_ldap_user(email, password):
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token), 200
    else:
        # Fallback to SQL database authentication
        user = User.query.filter_by(email=email).first()

        if user and user.password == password:  # In a real app, use hashed passwords
            access_token = create_access_token(identity=email)
            return jsonify(access_token=access_token), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401


# Helper function to connect to the IMAP server (iRedMail)
def connect_to_imap(username, password, imap_server="localhost"):
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(username, password)
        return mail
    except Exception as e:
        return None


# Helper function to list received emails (Inbox or Spam)
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

        # Construct sender email address
        sender = f"{username}@{domain}"
        smtp_server = "localhost"

        # Send the email via SMTP
        success, error_message = send_email(sender, recipient, subject, body, smtp_server=smtp_server, smtp_username=sender, smtp_password=password)

        if success:
            # Log email to SQL and MongoDB
            email_log = EmailLog(sender=sender, recipient=recipient, subject=subject, body=body)
            db.session.add(email_log)
            db.session.commit()
            
            log_email_to_mongo(sender, recipient, subject, body)

            return jsonify({"message": "Email sent successfully!"}), 200
        else:
            return jsonify({"error": error_message}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API to fetch inbox or spam emails (JWT-protected)
@app.route('/get-mails', methods=['POST'])
@jwt_required()
def get_mails():
    try:
        data = request.json
        domain = data.get('domain')
        username = data.get('username')
        password = data.get('password')
        folder = data.get('folder', 'INBOX')  # Default to INBOX, can be 'SPAM' or others

        if not all([domain, username, password]):
            return jsonify({"error": "Missing domain, username, or password"}), 400

        email_address = f"{username}@{domain}"
        imap_server = "localhost"

        # Connect to IMAP (iRedMail server)
        mail = connect_to_imap(email_address, password, imap_server)
        if not mail:
            return jsonify({"error": "Failed to connect to the email server"}), 500

        # Fetch emails from the specified folder
        emails = list_inbox_emails(mail, folder=folder)

        # Log fetched emails to MongoDB
        for email_item in emails:
            log_email_to_mongo(email_item['from'], email_address, email_item['subject'], "")

        mail.logout()

        return jsonify({"emails": emails}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


### Helper function to send an email using SMTP ###
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

        return True, None
    except Exception as e:
        return False, str(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
