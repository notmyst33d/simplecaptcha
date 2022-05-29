import os, asyncio, random, string, time, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from io import BytesIO

loop = asyncio.new_event_loop()
routes = web.RouteTableDef()

# Defaults, you can change them if you want
image_w = 120
image_h = 60

cache = {}
cache_max = 60 * 5
gc_sleep = 3

with open("types.json", "r") as f:
    captcha_types = json.loads(f.read())

captcha_host = os.environ.get("CAPTCHA_HOST", "http://localhost:6729")

def get_random_color():
    return (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))

def get_random_line_pos(scale):
    return (np.random.randint(0, image_w * scale),
            np.random.randint(0, image_h * scale),
            np.random.randint(0, image_w * scale),
            np.random.randint(0, image_h * scale))

def get_captcha(text, type):
    # Create new image
    image = Image.new("RGB", (image_w * type["scale"], image_h * type["scale"]), color=get_random_color() if type["randomize_bg_color"] else (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Open font
    text_font = ImageFont.truetype("font.otf", 24 * type["scale"])

    # Calculate the centered position of the text
    text_size = text_font.getsize(text)
    text_w = (image.size[0] / 2) - (text_size[0] / 2)
    text_h = (image.size[1] / 2) - (text_size[1] / 2) - (4 * type["scale"])

    # Draw text
    draw.text((text_w, text_h), text, font=text_font, fill=0)

    # Start applying effects
    noise = Image.fromarray(np.random.randint(0, 255, (image_h * type["scale"], image_w * type["scale"], 3), dtype=np.dtype("uint8")))

    for i in range(0, type["lines"]):
        draw.line(get_random_line_pos(type["scale"]), fill=0, width=type["lines_width"] * type["scale"])

    image = Image.blend(image, noise, alpha=type["noise_level"])

    # Save image in memory
    bio = BytesIO()
    image.save(bio, "JPEG")
    bio.seek(0)

    return bio

async def async_get_captcha(text, type):
    return await loop.run_in_executor(None, get_captcha, text, type)

async def garbage_collector_task():
    while True:
        try:
            count = 0
            run_time = time.time()
            keys = list(cache.keys())

            for key in keys:
                if cache[key]["gc"]:
                    del cache[key]
                    count += 1
                elif not cache[key]["gc"] and run_time > cache[key]["timestamp"] + cache_max:
                    del cache[key]
                    count += 1

            print(f"[Garbage Collector] {len(keys)} objects in cache, {count} objects collected in this run")
            await asyncio.sleep(gc_sleep)
        except:
            print("[Garbage Collector] Something went wrong while processing the cache")
            await asyncio.sleep(gc_sleep)

@routes.get("/captcha/{type}")
async def captcha_entry(req):
    if not captcha_types.get(req.match_info["type"]):
        return web.Response(text="Unknown captcha type", status=500, content_type="text/plain")

    # Create random captcha text
    text = "".join(random.choice(string.digits) for i in range(0, 6))

    # Create captcha image
    image = await async_get_captcha(text, captcha_types[req.match_info["type"]])

    # Create key and key ID
    key_id = os.urandom(16).hex().upper()
    key = os.urandom(16).hex().upper()

    shared_timestamp = time.time()

    # Save captcha info in the cache
    cache[key_id] = {
        "type": req.match_info["type"],
        "text": text,
        "image": image,
        "timestamp": shared_timestamp,
        "gc": False
    }

    # Save key info in the cache
    cache[key] = {
        "key_id": key_id,
        "timestamp": shared_timestamp,
        "gc": False
    }

    return web.json_response({
        "key_id": key_id,
        "image": f"{captcha_host}/image/{key_id}",
        "verify": f"{captcha_host}/verify/{key}/"
    })

@routes.get("/verify/{key}/{text}")
async def captcha_verify(req):
    key = req.match_info["key"]
    key_id = cache.get(key, {}).get("key_id")

    if not key_id:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

    captcha = cache.get(key_id)

    if captcha["text"] == req.match_info["text"]:
        cache[key_id]["gc"] = True
        cache[key]["gc"] = True
        return web.json_response({"type": cache[key_id]["type"]})
    else:
        return web.json_response({"type": cache[key_id]["type"]}, status=401)

@routes.get("/image/{key_id}")
async def captcha_image(req):
    key_id = req.match_info["key_id"]
    captcha = cache.get(key_id)

    if captcha:
        captcha["image"].seek(0)
        return web.Response(body=captcha["image"].read(), content_type="image/jpeg", headers={"Content-Disposition": f"inline; filename=\"{key_id}.jpg\""})
    else:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

if os.environ.get("ENABLE_USELESS_FEATURES"):
    # This is used for readme
    # Its useless for most deployments other than mine
    @routes.get("/random/{type}")
    async def captcha_random(req):
        if not captcha_types.get(req.match_info["type"]):
            return web.Response(text="Unknown captcha type", status=500, content_type="text/plain")

        text = "".join(random.choice(string.digits) for i in range(0, 6))
        image = await async_get_captcha(text, captcha_types[req.match_info["type"]])

        return web.Response(body=image.read(), content_type="image/jpeg", headers={"Content-Disposition": "inline; filename=\"showcase.jpg\""})

loop.create_task(garbage_collector_task())

app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 6729)), loop=loop)
