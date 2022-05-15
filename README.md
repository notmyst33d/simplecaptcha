# simplecaptcha
Simple captcha service

## API
### `GET /challenge`
Requires no extra parameters, returns this:
```
{
    "uuid": "8f7b9a86-1553-47cf-a90b-08591b31af1b",
    "challenge": "https://yourhost.com/challenge/8f7b9a86-1553-47cf-a90b-08591b31af1b",
    "submit": "https://yourhost.com/submit/8f7b9a86-1553-47cf-a90b-08591b31af1b",
    "verify": "https://yourhost.com/verify/24d09382-0727-45bd-a5d6-5ba2f5294222" <-- Intentionally different, it should be known only to the captcha server and the server that requested /challenge
}
```

`challenge` is used for getting captcha image, `submit` is used to submit the captcha solution, `verify` is used to verify if the user solved the captcha or not.

### `GET /challenge/{uuid}`
Requires no extra parameters, returns captcha image

### `GET /submit/{uuid}`
Requires `text` parameter with the captcha solution, returns 200 on success and 403 on failure

### `GET /verify/{uuid}`
Requires no extra parameters, returns 200 on success and 403 on failure, garbage collector will remove the captcha from the cache if 200 was returned
