from requests_oauthlib import OAuth2Session

def authenticate(auth_url, client_id, client_secret):

    oauth = OAuth2Session(client_id, ...)
    token = oauth.fetch_token(
        auth_url,
        authorization_response=authorization_response,
        client_secret=client_secret)
    return token

def main():
    pass

if __name__ == "__main__":
    main()
