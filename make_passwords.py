import bcrypt
import getpass

for username in ["Girija", "Signor Paolo"]:
    print(f"\nCreate a password for {username}:")
    password = getpass.getpass("Password: ")

    hashed = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    )

    print(f"\n{username} password hash:")
    print(hashed.decode("utf-8"))