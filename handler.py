#!/usr/bin/env python

# Most of the base infrastructure is based on this tutorial:
#  https://websockets.readthedocs.io/en/stable/intro/tutorial1.html

#Temporary. Will be removed when Game logic stuff is complete.
import pandas as pd 
import numpy as np
pd.set_option('mode.chained_assignment', None)

#Handles game logic
from simulation import Game

import asyncio
import websockets
import http
import signal
import os

import json

#For checking python version
import sys
#verification or else certain code (match) won't work.
assert sys.version_info >= (3, 10)


async def handler(websocket):
	#message = await websocket.recv()
	async for message in websocket:
		try:
			event = json.loads(message)

			#Start game and begin simulation
			if (event["type"] == "starting" and event["yes"]):
				game = Game()
				event = {
					"type": "baseGenome",
					"data": game.origin
				}

				await websocket.send(json.dumps(event))
				await runGame(websocket, game)
		except json.JSONDecodeError as e:
			print("Invalid JSON format: " + message)

#TODO: create new connection in case `except websockets.ConnectionClosedOK:`
async def runGame(websocket, game):
	print("printing stuff")
	paused = False

	#Requiring a "confirmation message" from root.js allows more synchronization between the cloud and server.
	async for message in websocket:
		try:
			event = json.loads(message)
		except json.JSONDecodeError as e:
			print("Invalid JSON format: " + message)
			continue
		#TODO: try event[type] or check to see if type even exists
		
		match event["type"]:
			case "starting":
				#Reminder that ~False = -1 and ~True = -2
				#Bug: baseGenome message sent by handler() but Init() is called before continue message can be sent from receiveMessage() in root.js.
				#Removing condition for break allows someone to restart the game in case this bug happens.
				if event["yes"]:
					print("Sorry about the bug.")
				break
			case "continue":
				game.forwardTime()
				await printTables(websocket, game)
				await asyncio.sleep(1)
			case "keyMod":
				game.modifyGene(event["index"], event["newChar"])
				print(game.origin)
			case "pause":
				paused = event["yes"]
			case _:
				print(event)

	print("Exiting game")


#Send all tables to JS
async def printTables(websocket, game):
	await websocket.send(json.dumps({"type": "table", "name":"Cells", "data": game.Cells.head(10).iloc[:, :-1].to_html()}))
	await websocket.send(json.dumps({"type": "table", "name":"FreeVirus", "data": game.FreeVirus.head(10).iloc[:, :-2].to_html()}))
	await websocket.send(json.dumps({"type": "table", "name":"InVirus", "data": game.InVirus.head(10).iloc[:, :-1].to_html()}))

	data = game.CellTotal.head(10).set_index('Gene')
	data.loc["Total"] = game.CellTotal.sum()
	data = data.astype(int)
	await websocket.send(json.dumps({"type": "table", "name":"CellTotal", "data": data.to_html()}))
	data = game.VirusTotal.head(10).set_index('Gene')
	data.loc["Total"] = game.VirusTotal.sum()
	data = data.astype(int)
	await websocket.send(json.dumps({"type": "table", "name":"VirusTotal", "data": data.to_html()}))


#######################################
####### Connection Handling ###########
#######################################

#From https://websockets.readthedocs.io/en/stable/howto/fly.html
#https://fly.io/docs/app-guides/continuous-deployment-with-github-actions/
#https://www.tutorialspoint.com/python_network_programming/python_http_server.htm
async def health_check(path, request_headers):
	if path == "/healthz":
		return http.HTTPStatus.OK, [], b"OK\n"

async def main():
	print("Starting...")
	# Set the stop condition when receiving SIGTERM.
	loop = asyncio.get_running_loop()
	stop = loop.create_future()
	loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
	async with websockets.serve(
		handler,
		host="",
		port=8001,
		process_request=health_check,
	):
		await stop

if __name__ == '__main__':
	asyncio.run(main())
