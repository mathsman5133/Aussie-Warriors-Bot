#Requests for making POST requests to supercell
import requests
#Json to convert dictionary to json dumps and to convert string to dictionary 
import json


def new_token():
    #Find current public IP
    currentIP = requests.get('http://ip.42.pl/short').text

    #Print.. Just here for debug purpose, can remove if you want
    #print(currentIP)

    #Define the Values for our token

    name = 'nameOfToken'    #This can stay same, no problems
    description = 'This is an example' #This can stay same, no problems
    cidrRanges = [currentIP] #It needs IP in this form


    #Start a session, in which we will be making request to log in and to generate new Token
    with requests.Session() as sess:

        #Define the login URL for login request
        loginURL = 'https://developer.clashofclans.com/api/login'
        #Define URL for Token creation request
        keyCreateURL = 'https://developer.clashofclans.com/api/apikey/create'

        '''Sensitive info here'''
        #Your developer account's email and password to login
        email='mathsman5132@gmail.com'
        password='creepy_crawley'

        #Define the dictionary of login data and convert it to JSON Dump
        loginData = json.dumps({'email':email,'password':password})

        #Define the header needed for login request (Server sends Error 403 if this is excluded)
        loginHeaders = {'content-type': 'application/json'}

        #Send a post request to server (i.e Login into your account)
        response = sess.post(loginURL,data=loginData,headers=loginHeaders)

        #Convert the response into a dictionary (We need this to get the temporary token which is used for Token Generation)
        responseDict = json.loads(response.text)

        #These are the cookies needed to create the Token
        game_api_token = responseDict['temporaryAPIToken']
        game_api_url = responseDict['swaggerUrl']
        session = sess.cookies['session']

        #Stich them together in the same format as browser (I didn't play much with it, maybe better way to do this exists..)
        cookies = 'session='+session+';'+'game-api-url='+game_api_url+';'+'game-api-token='+game_api_token

        #Define the header for Token Request
        tokenHeader = {'cookie': cookies,
                    'content-type': 'application/json'}

        #Data to be sent for our new token
        keyData = {'name': name, 'description': description, 'cidrRanges': cidrRanges}

        #POST request
        response = sess.post(keyCreateURL,data=json.dumps(keyData),headers=tokenHeader)

        #Again convert to dict to find the token
        responseDict = json.loads(response.text)

        newToken = responseDict['key']['key']   #Supercell is weird, this is how dictionary structure ends up being

        #Print new token to see
        return(newToken)


