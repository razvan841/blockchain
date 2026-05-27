from ipv8.keyvault.crypto import default_eccrypto

with open("razvan.pem", "rb") as f:
    key = default_eccrypto.key_from_private_bin(f.read())

print(key.pub().key_to_bin().hex())