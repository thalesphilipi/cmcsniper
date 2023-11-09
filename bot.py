import asyncio
import input
import requests
from telethon.sync import TelegramClient, events
from web3 import Web3

sum = None
signer = None
timeDelay = None
busdAdr = "0xe9e7cea3dedca5984780bafc599bd69add087d56"


def sleep(ms):
    asyncio.sleep(ms / 1000.0)


async def main():
    async with TelegramClient('session', api_id, api_hash) as client:
        print("You should now be connected.")
        print("Save this session to avoid logging in again:")
        print(await client.session.save())

        await client.send_message('me', 'Bot started')

        @client.on(events.NewMessage)
        async def on_new_message(event):
            message = event.raw_text
            rows = message.split("\n")
            if (
                rows[0].split(" ")[0] == "🔴"
                and int(rows[7].split("%")[0]) <= 5
                and int(rows[8].split("%")[0]) <= 5
                and (
                    (rows[4].split(" ").split(-1)[0] == "BUSD"
                     and float(rows[4].split(" ").split(-2)[0]) > 50000)
                    or (rows[4].split(" ").split(-1)[0] == "USDT"
                        and float(rows[4].split(" ").split(-2)[0]) > 50000)
                    or (rows[4].split(" ").split(-1)[0] == "BNB"
                        and float(rows[4].split(" ").split(-2)[0]) > 100)
                )
            ):
                address = rows[3].split(":")[1].replace(" ", "")
                await trade(address)

    await client.run_until_disconnected()


async def trade(address):
    sum_str = await input.text("Please enter your trade amount of BUSD for each trade (without decimals): ")
    sum = int(sum_str)
    time_delay_str = await input.text("Please enter time delay between buy and sell (in seconds): ")
    time_delay = int(time_delay_str)

    provider = Web3.HTTPProvider("https://bsc-dataseed.binance.org/")
    private_key = await input.text("Please enter your private key from metamask: ")
    signer = Web3.toChecksumAddress(Web3.toHex(Web3.toBytes(hexstr=private_key)))

    w3 = Web3(provider)
    nonce = w3.eth.getTransactionCount(signer)

    gas_price = w3.toWei(5, 'gwei')

    # Build and sign the transaction
    tx = {
        'from': signer,
        'to': address,
        'value': w3.toWei(sum, 'ether'),
        'gas': 21000,
        'gasPrice': gas_price,
        'nonce': nonce,
    }
    signed_tx = w3.eth.account.signTransaction(tx, private_key)

    print(f"swap BUSD => {address}")

    # Send the transaction
    tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    receipt = w3.eth.waitForTransactionReceipt(tx_hash)

    print(f"Transaction receipt: {receipt}")
    print(f"Waiting for {time_delay} seconds before selling...")
    sleep(time_delay * 1000)

    balance = requests.get(
        f"https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress={address}&address={signer}&tag=latest&apikey=IWPP5MJZX5XFQZKYE9CJ5IDEQAGX372AJZ").json()
    balance = int(balance['result'])

    allowance_data = {
        'method': 'approve',
        'params': {
            'owner': signer,
            'spender': '0x11111112542D85B3E0A6E3146E87CfE3bc0C6eB48',  # 1Inch router contract
            'value': balance,
        }
    }
    tx_data = requests.post("https://api.1inch.exchange/v3.0/56/approve/transaction", json=allowance_data).json()
    gas_price = w3.toWei(10, 'gwei')
    tx_data['gas'] = int(tx_data['gas'])
    tx_data['gasPrice'] = gas_price

    print(f"approve {address}")

    # Send the approval transaction
    allowance_receipt = w3.eth.waitForTransactionReceipt(tx_data)
    print(f"Approval receipt: {allowance_receipt}")

    swap_data = {
        'fromTokenAddress': address,
        'toTokenAddress': busdAdr,
        'amount': balance,
        'fromAddress': signer,
        'slippage': 5,
    }
    swap_result = requests.get(f"https://api.1inch.exchange/v3.0/56/swap", params=swap_data).json()
    gas_price = w3.toWei(5, 'gwei')
    tx = swap_result['tx']
    tx['gas'] = int(tx['gas'])
    tx['gasPrice'] = gas_price
    tx['value'] = int(tx['value'])

    print(f"swap {address} => BUSD")

    # Send the swap transaction
    swap_receipt = w3.eth.waitForTransactionReceipt(tx)
    print(f"Swap receipt: {swap_receipt}")

    profit_percentage = ((swap_result['toTokenAmount'] / 1e18 - sum) / sum) * 100
    print(f"profit: {profit_percentage:.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
