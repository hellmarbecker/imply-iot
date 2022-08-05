import yaml
import json
import time
import argparse, sys, logging
import requests


def getToken(token_url, client_id, client_secret):

    token = None
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    } 
    logging.debug(f'token request payload: {payload}')
    r = requests.post(token_url, data=payload)
    logging.debug(f'status code: {r.status_code}')
    logging.debug(f'response: {r.text}')
    if r.status_code == 200:
        token = json.loads(r.text)

    return token

def sendEvent(event_url, table_id, bearer_token, e):

#    r = requests.post( ... )
    return r

# Check configuration

def checkConfig(cfg):

    # Raise an exception if anything is wrong with the configuration
    pass

# Read configuration

def readConfig(ifn):
    logging.debug(f'reading config file {ifn}')
    with open(ifn, 'r') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
        # get include files if present
        for inc in cfg.get("IncludeOptional", []):
            try:
                logging.debug(f'reading include file {inc}')
                cfg.update(yaml.load(open(inc), Loader=yaml.FullLoader))
            except FileNotFoundError:
                logging.debug(f'optional include file {inc} not found, continuing')
        logging.debug(f'Configuration: {cfg}')
        checkConfig(cfg)
        return cfg

def main():

    logLevel = logging.INFO
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', help='Enable debug logging', action='store_true')
    parser.add_argument('-q', '--quiet', help='Quiet mode (overrides Debug mode)', action='store_true')
    parser.add_argument('-f', '--config', help='Configuration file for session state machine(s)', required=True)
    parser.add_argument('-m', '--mode', help='Mode for session state machine(s)', default='default')
    parser.add_argument('-n', '--dry-run', help='Write to stdout instead of Kafka',  action='store_true')
    args = parser.parse_args()

    if args.debug:
        logLevel = logging.DEBUG
    if args.quiet:
        logLevel = logging.ERROR

    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logLevel)

    cfgfile = args.config
    config = readConfig(cfgfile)
    # sys.exit(0)
    selector = args.mode

    if args.dry_run:
        # output to stdout
        pass
    else:
        # use HTTP endpoint
        polarisConf = config['Polaris']

    minSleep = config['General']['minSleep']
    if minSleep is None:
        minSleep = 0.01
    maxSleep = config['General']['maxSleep']
    if maxSleep is None:
        maxSleep = 0.04

    # main loop
    
    myToken = None
    while True:
        
        if myToken is None:
            logging.info('getting new Token')
            myToken = getToken(polarisConf['token_url'], polarisConf['client_id'], polarisConf['client_secret'])
            logging.debug(f'returned Token: {myToken}')
            timeToken = time.time()
            timeExpiry = timeToken + myToken['expires_in']
            logging.info(f'token obtained at {timeToken}, expires at {timeExpiry}')

        dataRec = {
            "__time": time.time() * 1000.0,
            "var": "a", 
            "val": 1.0
        }

        response = sendEvent(
            polarisConf['eventURL'],
            polarisConf['tableID'],
            myToken['access_token'],
            dataRec
        )
        if response.status_code != 200:
        
            if response.status_code == 401 and 'token expired' in response.text:
                logging.info('token expired, resetting token')
            else:
                logging.error(f'sendEvent returned status {response.status_code} with message {response.text}')
             

if __name__ == "__main__":
    main()
