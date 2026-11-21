from app import app, init_db


init_db()


if __name__ == "__main__":
    from waitress import serve

    serve(app, host="127.0.0.1", port=5000)
