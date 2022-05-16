# simplecaptcha
Simple captcha service

## Environment variables
`PORT` - The port to run the HTTP server on  
`CAPTCHA_HOST` - The host where the service is running, for example: `https://captcha.myhost.com`

## How to use it
1. Make your own endpoint for the captcha and send `key_id` and `image` fields to the user
2. Store the data from `/captcha/{type}` in some temporary storage
3. Make sure your website/app sends `key_id` and the captcha solution along with a request that requires a captcha
4. When you received the request that requires the captcha, get the data from the temporary storage using `key_id` field from the request
5. Send a request to `verify` URL + the captcha solution, you should get something like `https://captcha.myhost.com/verify/288043316EA012B8E87DD151C912E08D/123456`
6. Check the response code(look at API docs for more info)
7. Check the captcha type, make sure the type is the same as you requested in `/captcha/{type}`
8. Done! Now your website/app is more secure from the bots

## API
### `GET /captcha/{type}`
Requires no extra parameters, returns 200 on success

JSON:
```
{
    "key_id": "1A0CB4E8840E322A05526E712386AF80",
    "image": "https://captcha.myhost.com/image/1A0CB4E8840E322A05526E712386AF80",
    "verify": "https://captcha.myhost.com/verify/288043316EA012B8E87DD151C912E08D/"
}
```

`key_id` is used for keeping track of the captcha(can be sent to a user), `image` is used for getting captcha image(can be sent to a user), `verify` is used to submit the captcha solution and to verify if the user solved the captcha or not(should only be kept on the server that requested the captcha)

Available types: `easy`, `normal`, `hard`

### `GET /image/{key_id}`
Requires no extra parameters, returns 200 and the captcha image on success and 404 when captcha is not present in the cache

### `GET /verify/{key}/{solution}`
Requires `key` and `solution` parameters in the URL, returns 200 on success, 403 on failure and 404 when captcha is not present in the cache, garbage collector will remove the captcha from the cache if 200 was returned

JSON:
```
{
    "type": "easy"
}
```
