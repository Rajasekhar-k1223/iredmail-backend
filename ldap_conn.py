# from cmath import e
# from ldap3 import Server, Connection, ALL, NTLM

# # Configuration variables
# LDAP_SERVER = 'ldap://localhost'  # Replace with your LDAP server URL
# LDAP_USER_DN = 'cn=admin,dc=example,dc=com'  # Replace with your admin DN
# LDAP_PASSWORD = 'Admin@123'  # Replace with your admin password

# def connect_to_ldap():
#     # Create a server object with the given URL
#     server = Server(LDAP_SERVER, get_info=ALL)

#     try:
#         # Establish a connection to the LDAP server
#         conn = Connection(server, user=LDAP_USER_DN, password=LDAP_PASSWORD, auto_bind=True)
#         print("Connected to LDAP server.")
#         return conn
#     except e:
#         print(f"Failed to connect to LDAP server: {e}")
#         return None

# def add_user(email, password, first_name, last_name):
#     conn = connect_to_ldap()
#     if not conn:
#         return False

#     # Create a new user entry
#     user_dn = f"uid={email},ou=users,dc=example,dc=com"  # Adjust the DN as per your directory structure
#     user_entry = Entry(user_dn, 
#                        objectClass=['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
#                        uid=email,
#                        cn=first_name,
#                        sn=last_name,
#                        userPassword=password)

#     # Attempt to add the user
#     try:
#         conn.add(user_entry)
#         print(f"User {email} added successfully.")
#         return True
#     except Exception as e:
#         print(f"Failed to add user: {e}")
#         return False


# # Example function to authenticate a user
# def authenticate_user(email, password):
#     conn = connect_to_ldap()
#     if not conn:
#         return False

#     # Search for the user in the LDAP directory
#     search_filter = f"(mail={email})"
#     conn.search('dc=example,dc=com', search_filter, attributes=['cn', 'mail'])

#     if conn.entries:
#         user_dn = conn.entries[0].entry_dn
#         # Attempt to bind as the found user
#         user_conn = Connection(server, user=user_dn, password=password)

#         if user_conn.bind():
#             print("User authenticated successfully.")
#             user_conn.unbind()
#             return True
#         else:
#             print("User authentication failed.")
#             return False

#     print("User not found.")
#     return False

# # Example usage
# if __name__ == "__main__":
#     email = input("Enter user email: ")
#     password = input("Enter user password: ")
#     authenticate_user(email, password)

from flask import Flask, request, jsonify
from ldap3 import Server, Connection, ALL, Entry

app = Flask(__name__)

# Configuration variables
LDAP_SERVER = 'ldap://localhost:389'  # Replace with your LDAP server URL
LDAP_USER_DN = 'cn=admin,dc=example,dc=com'  # Replace with your admin DN
LDAP_PASSWORD = 'Admin@123'  # Replace with your admin password

def connect_to_ldap():
    # Create a server object with the given URL
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        # Establish a connection to the LDAP server
        conn = Connection(server, user=LDAP_USER_DN, password=LDAP_PASSWORD, auto_bind=True)
        print("Connected to LDAP server.")
        return conn
    except Exception as e:
        print(f"Failed to connect to LDAP server: {e}")
        return None


@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')

    conn = connect_to_ldap()
    if not conn:
        return jsonify({"error": "Failed to connect to LDAP server."}), 500

    # Create a new user entry
    user_dn = f"uid={email},ou=users,dc=example,dc=com"  # Adjust the DN as per your directory structure
    user_entry = Entry(user_dn, 
                       objectClass=['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
                       uid=email,
                       cn=first_name,
                       sn=last_name,
                       userPassword=password)

    # Attempt to add the user
    try:
        conn.add(user_entry)
        return jsonify({"message": f"User {email} added successfully."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/authenticate_user', methods=['POST'])
def authenticate_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = connect_to_ldap()
    if not conn:
        return jsonify({"error": "Failed to connect to LDAP server."}), 500

    # Search for the user in the LDAP directory
    search_filter = f"(mail={email})"
    conn.search('dc=example,dc=com', search_filter, attributes=['cn', 'mail'])

    if conn.entries:
        user_dn = conn.entries[0].entry_dn
        # Attempt to bind as the found user
        user_conn = Connection(conn.server, user=user_dn, password=password)

        if user_conn.bind():
            user_conn.unbind()
            return jsonify({"message": "User authenticated successfully."}), 200
        else:
            return jsonify({"error": "User authentication failed."}), 401

    return jsonify({"error": "User not found."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)

