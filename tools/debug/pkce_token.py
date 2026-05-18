import base64
import hashlib
import secrets

def generate_pkce():
    # 1. 產生 Code Verifier (高熵隨機字串)
    code_verifier = secrets.token_urlsafe(64)
    
    # 2. 產生 Code Challenge (SHA256 -> Base64URL)
    code_challenge_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_hash).decode('ascii').replace('=', '')
    
    return code_verifier, code_challenge

verifier, challenge = generate_pkce()
print(f"Code Verifier: {verifier}")
print(f"Code Challenge: {challenge}")
