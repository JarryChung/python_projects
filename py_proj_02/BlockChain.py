#
# Jarry Chung
# 2018-4-3
#

import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests


class BlockChain(object):       # BlockChain类用来管理链条
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        # 创建创世块
        self.new_block(previous_hash=1, proof=100)
        self.nodes = set()

    def new_block(self, proof, previous_hash):
        # 新建一个区块
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        # 重置当前交易链
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transactions(self, sender, recipient, amonut):
        # 新建交易信息，该信息将加入到下一个待挖的区块中
        self.current_transactions.append(
            {
                'sender': sender,
                'recipient': recipient,
                'amount': amonut
            }
        )
        return self.last_block['index'] + 1

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print('{last_block}')
            print('{block}')
            print("------------------")
            # 检查
            if block['previous_hash'] != self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return  False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        # 使用共识算法解决冲突
        # 使用网络中最长的链
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)
        for node in neighbours:
            response = requests.get('http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

    @staticmethod
    def hash(block):
        # 哈希块，生成块的ＳＨＡ－２５６　ｈａｓｈ值
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # 返回最新的区块
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        # 工作量证明
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        # 验证
        guess = '{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')
blockchain = BlockChain()


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    # 给工作量证明的节点提供奖励
    # 发送者为“０”表明是新挖出的币
    blockchain.new_transactions(
        sender="0",
        recipient=node_identifier,
        amonut=1
    )
    block = blockchain.new_block(proof)
    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }
    return jsonify(response), 200


@app.route('/transactions.new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing value', 400
    # 新建一个交易
    index = blockchain.new_transactions(values['sender'], values['recipient'], values['amount'])
    response = {'message': 'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': "New node haa been added.",
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': "The chain was replaced.",
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': "The chain is authoritative.",
            'chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)