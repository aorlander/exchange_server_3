from flask import Flask, request, g
from flask_restful import Resource, Api
from sqlalchemy import create_engine, select, MetaData, Table
from flask import jsonify
import json
import eth_account
import algosdk
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import load_only

from models import Base, Order, Log
engine = create_engine('sqlite:///orders.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

app = Flask(__name__)

#These decorators allow you to use g.session to access the database inside the request code
@app.before_request
def create_session():
    g.session = scoped_session(DBSession) #g is an "application global" https://flask.palletsprojects.com/en/1.1.x/api/#application-globals

@app.teardown_appcontext
def shutdown_session(response_or_exc):
    g.session.commit()
    g.session.remove()

"""
-------- Helper methods (feel free to add your own!) -------
"""
#If the signature does not verify, do not insert the order into the “Order” table. 
#Instead, insert a record into the “Log” table, with the message field set to be json.dumps(payload).
def log_message(d):
    time = datetime.now()
    log = Log(logtime=time, message=d)
    session.add(log)
    session.commit()
    pass

"""
---------------- Endpoints ----------------
"""
#Accept POST data in JSON format. 
#Orders should have two fields “payload” and "sig".
#The payload will contain the following fields, ‘sender_pk’,’receiver_pk,’buy_currency’,’sell_currency’,’buy_amount’,’sell_amount’,’platform’.
@app.route('/trade', methods=['POST'])
def trade():
    if request.method == "POST":
        content = request.get_json(silent=True)
        print( f"content = {json.dumps(content)}" )
        columns = [ "sender_pk", "receiver_pk", "buy_currency", "sell_currency", "buy_amount", "sell_amount", "platform" ]
        fields = [ "sig", "payload" ]
        error = False
        for field in fields:
            if not field in content.keys():
                print( f"{field} not received by Trade" )
                print( json.dumps(content) )
                log_message(content)
                return jsonify( False )
        
        error = False
        for column in columns:
            if not column in content['payload'].keys():
                print( f"{column} not received by Trade" )
                error = True
        if error:
            print( json.dumps(content) )
            log_message(content)
            return jsonify( False )
        
        #check whether “sig” is a valid signature of json.dumps(payload), using the signature algorithm specified by the platform field
        s_pk = content['payload']['sender_pk'] 
        r_pk = content['payload']['receiver_pk'] 
        buy_ccy = content['payload']['buy_currency'] 
        sell_ccy = content['payload']['sell_currency'] 
        buy_amt = content['payload']['buy_amount'] 
        sell_amt = content['payload']['sell_amount'] 
        platform = content['payload']['platform']
        sig = content['sig']
        payload = json.dumps(content['payload'])
        response = False
        if platform=='Ethereum':
            eth_encoded_msg = eth_account.messages.encode_defunct(text=payload)
            if eth_account.Account.recover_message(eth_encoded_msg,signature=sig) == s_pk:
                response = True
        if platform=='Algorand':
            if algosdk.util.verify_bytes(payload.encode('utf-8'),sig,s_pk):
                response = True

        #If the signature verifies, all of the fields under the ‘payload’ key should be stored in the “Order” table EXCEPT for 'platform’.
        if response == True:
            order = Order( sender_pk=s_pk, receiver_pk=r_pk, buy_currency=buy_ccy, sell_currency=sell_ccy, buy_amount=buy_amt, sell_amount=sell_amt)
            session.add(order)
            session.commit()
        #If the signature does not verify, do not insert the order into the “Order” table. 
        #Instead, insert a record into the “Log” table, with the message field set to be json.dumps(payload).
        if response == False:
            leg_message(payload)

        return jsonify(response)

#Return a list of all orders in the database. The response should be a list of orders formatted as JSON. 
# Each order should be a dict with (at least) the following fields ("sender_pk", "receiver_pk", 
# "buy_currency", "sell_currency", "buy_amount", "sell_amount", “signature”).
@app.route('/order_book')
def order_book():
    orders = session.query(Order).all()
    #orders = g.session query to get all entries
    list_orders = []
    for order in orders:
        o = {
            "sender_pk": order.sender_pk, 
            "receiver_pk": order.receier_pk, 
            "buy_currency": order.buy_currency, 
            "sell_currency": order.sell_currency, 
            "buy_amount": order.buy_amount, 
            "sell_amount": order.sell_amount, 
            "signature": order.signature }
        list_orders.add(o)

    d = json.dumps(list_orders)
    result = {
        "data": d
    }
    return jsonify(result)

if __name__ == '__main__':
    app.run(port='5002')
