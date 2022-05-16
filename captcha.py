import os, asyncio, random, string, time
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

captcha_host = os.environ.get("CAPTCHA_HOST", "http://localhost:6729")

def get_random_color():
    return (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))

def get_random_line_pos(scale):
    return (np.random.randint(0, image_w * scale),
            np.random.randint(0, image_h * scale),
            np.random.randint(0, image_w * scale),
            np.random.randint(0, image_h * scale))

async def async_get_random_color():
    return await loop.run_in_executor(None, get_random_color)

async def async_get_random_line_pos(scale):
    return await loop.run_in_executor(None, get_random_line_pos, scale)

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

@routes.get("/challenge/{type}")
async def captcha_challenge(req):
    captcha_type = req.match_info["type"]

    if captcha_type == "easy":
        scale = 1
        lines = 12
        lines_width = 2
        noise_level = 0
        randomize_bg_color = False
    elif captcha_type == "normal":
        scale = 1
        lines = 6
        lines_width = 4
        noise_level = 0.4
        randomize_bg_color = False
    elif captcha_type == "hard":
        scale = 1
        lines = 6
        lines_width = 4
        noise_level = 0.25
        randomize_bg_color = True
    else:
        return web.Response(text="Unknown captcha type", status=500, content_type="text/plain")

    text = "".join(random.choice(string.digits) for i in range(0, 6))

    # Create new image
    image = Image.new("RGB", (image_w * scale, image_h * scale), color=await async_get_random_color() if randomize_bg_color else (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Open font
    text_font = ImageFont.truetype("font.otf", 24 * scale)

    # Calculate the centered position of the text
    text_size = text_font.getsize(text)
    text_w = (image.size[0] / 2) - (text_size[0] / 2)
    text_h = (image.size[1] / 2) - (text_size[1] / 2) - (4 * scale)

    # Draw text
    draw.text((text_w, text_h), text, font=text_font, fill=0)

    # Start applying effects
    noise = Image.fromarray(np.random.randint(0, 255, (image_h * scale, image_w * scale, 3), dtype=np.dtype("uint8")))

    for i in range(0, lines):
        draw.line(await async_get_random_line_pos(scale), fill=0, width=lines_width * scale)

    image = Image.blend(image, noise, alpha=noise_level)

    # Save image in memory
    bio = BytesIO()
    image.save(bio, "JPEG")

    # Key ID and the key
    key_id = os.urandom(16).hex().upper()
    key = os.urandom(16).hex().upper()

    shared_timestamp = time.time()

    cache[key_id] = {
        "type": captcha_type,
        "image": bio,
        "solution": text,
        "timestamp": shared_timestamp,
        "gc": False
    }

    cache[key] = {
        "key_id": key_id,
        "timestamp": shared_timestamp,
        "gc": False
    }

    return web.json_response({
        "image": f"{captcha_host}/image/{key_id}",
        "verify": f"{captcha_host}/verify/{key}/"
    })

@routes.get("/verify/{key}/{solution}")
async def captcha_verify(req):
    solution = req.match_info["solution"]
    key = req.match_info["key"]
    key_id = cache.get(key, {}).get("key_id")

    if not key_id:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

    captcha = cache.get(key_id)

    if captcha["solution"] == solution:
        cache[key_id]["gc"] = True
        cache[key]["gc"] = True
        return web.json_response({
            "success": True,
            "type": cache[key_id]["type"]
        })
    else:
        return web.json_response({
            "success": False,
            "type": cache[key_id]["type"]
        }, status=403)

@routes.get("/image/{key_id}")
async def captcha_image(req):
    key_id = req.match_info["key_id"]
    captcha = cache.get(key_id)

    if captcha:
        captcha["image"].seek(0)
        return web.Response(body=captcha["image"].read(), content_type="image/jpeg", headers={"Content-Disposition": f"inline; filename=\"{key_id}.jpg\""})
    else:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

loop.create_task(garbage_collector_task())

app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 6729)), loop=loop)
