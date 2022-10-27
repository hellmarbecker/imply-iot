#!/usr/bin/env python
"""a simple data generator that sends to a Kafka broker"""
import sys
import json
import yaml
import time
import random
from confluent_kafka import Producer
import socket
import argparse
import logging
import requests
from mergedeep import merge


def checkConfig(cfg):

    # Raise an exception if anything is wrong with the configuration
    pass

# Read configuration

def readConfig(ifn):
    logging.debug(f'reading config file {ifn}')
    with open(ifn, 'r') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
        includecfgs = []
        # get include files if present
        for inc in cfg.get("IncludeOptional", []):
            try:
                logging.debug(f'reading include file {inc}')
                c = yaml.load(open(inc), Loader=yaml.FullLoader)
                includecfgs.append(c)
            except FileNotFoundError:
                logging.debug(f'optional include file {inc} not found, continuing')
        merge(cfg, *includecfgs)
        logging.info(f'Configuration: {cfg}')
        checkConfig(cfg)
        return cfg


def generate(asset_0, asset_1, interval_ms, inject_error, emit):
    """generate data and send it to a Kafka broker"""

    interval_secs = interval_ms / 1000.0
    random.seed()
    iteration = 0

    #extract assets dimensions details
    asset_0_label = asset_0.get("label","asset_0")
    asset_0_nb_assets = asset_0.get("assets","3")
    asset_0_nb_dimensions = asset_0.get("dimensions","3")
    asset_0_dimensions_labels = asset_0.get("dimension_labels",[])
    asset_0_dimensions_types = asset_0.get("dimension_types",[])
    asset_0_dimensions_values = asset_0.get("dimension_values",[])
    asset_1_label = asset_1.get("label","asset_1")
    asset_1_nb_assets = asset_1.get("assets","3")
    asset_1_nb_dimensions = asset_1.get("dimensions","3")
    asset_1_dimensions_labels = asset_1.get("dimension_labels",[])
    asset_1_dimensions_types = asset_1.get("dimension_types",[])
    asset_1_dimensions_values = asset_1.get("dimension_values",[])
    asset_1_nb_metrics = asset_1.get("metrics",3)
    asset_1_metrics_values = asset_1.get("metrics_values")
    asset_1_metrics_labels = asset_1.get("metrics_labels")


    while True:
        iteration = iteration+1

        batch = []
        data = {
            "__time": int(time.time()*1000)
        }

        for a0 in range(asset_0_nb_assets):

            #GENERIC: generate asset_0 IDs
            data[asset_0_label+"_id"] = asset_0_label+"_" + str(a0)

            #GENERIC: generate asset_0 dimensions
            for key in range(asset_0_nb_dimensions):
                values = asset_0_dimensions_values.get("d_" + str(key))
                labels = asset_0_dimensions_labels.get("d_" + str(key))
                types = asset_0_dimensions_types.get("d_" + str(key))
                if types == "fixed":
                    data[labels] = values[a0]
                else:
                    if types == "high_cardinality":
                        data[labels] = labels + "_" + str(random.randint(0, values + 1))

            for a1 in range(asset_1_nb_assets):
                #GENERIC: generate asset_1 IDs
                data[asset_1_label+"_id"] = asset_1_label+"_" + str(a0)+"_"+str(a1)

                #GENERIC: generate asset_1 dimensions
                for key in range(asset_1_nb_dimensions):
                    values = asset_1_dimensions_values.get("d_" + str(key))
                    labels = asset_1_dimensions_labels.get("d_" + str(key))
                    types = asset_1_dimensions_types.get("d_" + str(key))
                    if types == "fixed":
                        data[labels] = values[a1]
                    else:
                        if types == "high_cardinality":
                            data[labels] = labels + "_" + str(random.randint(0, values + 1))

                #GENERIC: generate metrics
                for key in range(asset_1_nb_metrics):
                    min_val, max_val = asset_1_metrics_values.get("m_" + str(key))
                    label = asset_1_metrics_labels.get("m_" + str(key))
                    data[label] = random.randint(min_val, max_val)
              
                #Custom: Implement your abnormal behavior here ->
                if (iteration == 10):
                    data["rejected"] = random.randint(0, 3)
                if (a0 == 0 and (a1 == 0 or a1 == 4)):
                    # that's the case of the plant that solved the issue
                    data["machine_configuration"] = "multi_layer_custom"            
                if (inject_error == 'true'):
                    if (a0 == 4 and (a1 == 0 or a1 == 4)):
                        data["rejected"] = random.randint(1, 2)
                        data["temperature"] = random.randint(60, 65)
                        data["vibration"] = random.randint(120, 130)
                        data["material"] = "silicon_multi_layers"
                # -> end of abnormal behavior

                #GENERIC: publish the data
                k = data[asset_0_label+"_id"]
                v = json.dumps(data)
                logging.debug(f'before emit, value={v}')
                batch.append((k, v))

        msecs_spent = emit(batch)
        secs_left = interval_secs - msecs_spent / 1000.0
        if secs_left > 0.0:
            time.sleep(secs_left)

        if (iteration == 10):
            iteration = 0


def getToken(token_url, client_id, client_secret):

    token = None
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    logging.info(f'token request payload: {payload}')
    r = requests.post(token_url, data=payload)
    logging.info(f'status code: {r.status_code}')
    logging.info(f'response: {r.text}')
    if r.status_code == 200:
        token = json.loads(r.text)

    return token

        
def polarisEmitFunc(config):

    myToken = None
    polarisConf = config['Polaris']
    if myToken is None:
        logging.info('getting new Token')
        myToken = getToken(polarisConf['token_url'], polarisConf['client_id'], polarisConf['client_secret'])
        logging.info(f'returned Token: {myToken}')
        timeToken = time.time()
        timeExpiry = timeToken + myToken['expires_in']
        logging.info(f'token obtained at {timeToken}, expires at {timeExpiry}')
    myTokenString = myToken['access_token']

    def emitFunc(batch):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {myTokenString}'
        }
        logging.debug(f'headers={headers}')

        body = "".join([ v+"\n" for (k, v) in batch ])
        t1 = time.time()
        r = requests.post(polarisConf['table_url'], headers=headers, data=body, allow_redirects=False)
        dt_msec = 1000.0 * (time.time() - t1)
        logging.debug(f'request headers: {r.request.headers}')
        logging.debug(f'request body: {r.request.body}')
        logging.info(f'request took {dt_msec} msecs. status code: {r.status_code}')
        logging.debug(f'response: {r.text}')
        return dt_msec

    return emitFunc


def kafkaEmitFunc(config):

    kafkaconf = config['Kafka']
    topic = kafkaconf.get("topic", "simulator")
    # remove the topic so the rest can go into the producer properties directly
    del kafkaconf['topic']
    kafkaconf['client.id'] = socket.gethostname()
    brokers = kafkaconf.get("bootstrap.servers", "localhost:9092")
    producer = Producer(kafkaconf)

    def emitFunc(batch):
        t1 = time.time()
        for (k, v) in batch:
            producer.produce(topic, key=k, value=v)
            producer.poll(0)
        dt_msec = 1000.0 * (time.time() - t1)
        return dt_msec

    return emitFunc


def stdoutEmitFunc(config):

    def emitFunc(batch):
        for (k, v) in batch:
            print(v, flush=True)
        return 0.0

    return emitFunc


def main():
    """main entry point, load and validate config and call generate"""

    logLevel = logging.INFO
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', help='Enable debug logging', action='store_true')
    parser.add_argument('-f', '--config', help='Configuration file for session state machine(s)', required=True)
    parser.add_argument('-k', '--kafka', help='Write to Kafka', action='store_true')
    parser.add_argument('-m', '--mode', help='Mode for session state machine(s)', default='default')
    parser.add_argument('-n', '--dry-run', help='Write to stdout instead of Kafka', action='store_true')
    parser.add_argument('-p', '--polaris', help='Write to Polaris API', action='store_true')
    parser.add_argument('-q', '--quiet', help='Quiet mode (overrides Debug mode)', action='store_true')
    args = parser.parse_args()

    if args.debug:
        logLevel = logging.DEBUG
    if args.quiet:
        logLevel = logging.ERROR

    if args.mode == 'default':
        inject_error = 'false'
    else:
        inject_error = 'true'

    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logLevel)

    logging.debug(f'args: {args}')

    cfgfile = args.config

    try:
        config = readConfig(cfgfile)

        sys.exit(0)

        #prepare metrics configurations
        misc_config = config.get("misc", {})
        interval_ms = misc_config.get("interval_ms", 500)
        devmode = misc_config.get("devmode", False)

        #prepare assets
        asset_0 = config.get("asset_0",{})
        asset_1 = config.get("asset_1",{})
        

        if args.dry_run:
            emit = stdoutEmitFunc(config)
        elif args.kafka:
            emit = kafkaEmitFunc(config)
        elif args.polaris:
            emit = polarisEmitFunc(config)
        else:
            # no option => fall back to stdout
            emit = stdoutEmitFunc(config)

        #Start simulation
        generate(asset_0, asset_1, interval_ms, inject_error, emit)

    except IOError as error:
        print("Error opening config file '%s'" % cfgfile, error)

if __name__ == '__main__':
    main()
