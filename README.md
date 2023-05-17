# HH_API_resume_push

This script for pushing your resumes on HH

Preparing:
1. You need to install dependencies:
    pip install -r requirements
2. You need to create to files:
    a. auth.json
    b. config.ini
   structure of auth.json:
      {
         "email": "your_EMAIL@example.com",
         "password": "your_password"
      }
      
    structure config.ini:
    [app_auth]
    client_id = you need to register you app in dev.hh.ru
    client_secret = you need to register you app in dev.hh.ru
    redirect_uri = https://oauth.pstmn.io/v1/callback
    authorization_base_url = https://hh.ru/oauth/authorize
    token_url = https://hh.ru/oauth/token
    token_expire_date = script automatic writing this parameter
    refresh_token = script automatic writing this parameter
    token = script automatic writing this parameter
