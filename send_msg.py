# CONFIG
ADDR = '127.0.0.1'
PORT_LISTEN = 5701
PORT_SEND = 5700

import socket
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s')

# type=group/private(群聊/私聊)
# to=account(群号/好友号)
# msg=message
def send_msg(type,to,msg):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    msg = '{}'.format(msg)

    try:
        client.connect((ADDR, PORT_SEND))
        # 将字符中的特殊字符进行url编码
        msg = msg.replace(" ", "%20")
        msg = msg.replace("\n", "%0a")

        if type == 'group':
            payload = "GET /send_group_msg?group_id=" + str(
                to) + "&message=" + msg + " HTTP/1.1\r\nHost:" + ADDR + ":" + str(PORT_SEND) + "\r\nConnection: close\r\n\r\n"
        elif type == 'private':
            payload = "GET /send_private_msg?user_id=" + str(
                to) + "&message=" + msg + " HTTP/1.1\r\nHost:" + ADDR + ":" + str(PORT_SEND)  + "\r\nConnection: close\r\n\r\n"

        client.send(payload.encode("utf-8"))
    except Exception as exp:
        logging.warning(exp)
        return exp
    
    client.close()
    return None
