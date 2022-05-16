# simplecaptcha
Simple captcha service

## Environment variables
`PORT` - The port to run the HTTP server on  
`CAPTCHA_HOST` - The host where the service is running, for example: `https://captcha.myhost.com`

## API
### `GET /challenge/{type}`
Requires no extra parameters, returns 200 on success

JSON:
```
{
    "image": "https://captcha.myhost.com/image/1A0CB4E8840E322A05526E712386AF80",
    "verify": "https://captcha.myhost.com/verify/288043316EA012B8E87DD151C912E08D/" <-- Intentionally different, it should be known only to the captcha server and the server that requested /challenge
}
```

`image` is used for getting captcha image, `verify` is used to submit the captcha solution and to verify if the user solved the captcha or not

Available types: `easy`, `normal`, `hard`

### `GET /image/{key_id}`
Requires no extra parameters, returns 200 and the captcha image on success and 404 when captcha is not present in the cache

### `GET /verify/{key}/{solution}`
Requires `key` and `solution` parameters in the URL, returns 200 on success, 403 on failure and 404 when captcha is not present in the cache, garbage collector will remove the captcha from the cache if 200 was returned

JSON:
```
{
    "success": true,
    "type": "easy"
}
```
