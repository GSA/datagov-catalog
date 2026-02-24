import os

from app import create_app

# cloud.gov sets VCAP_APPLICATION; "production" gives https in url_for()
app = create_app(
    config_name="production" if os.getenv("VCAP_APPLICATION") else "local"
)

if __name__ == "__main__":
    app.run(debug=False, port=8080)
