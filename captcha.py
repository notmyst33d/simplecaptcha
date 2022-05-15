import asyncio, random, string, uuid, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from io import BytesIO

loop = asyncio.new_event_loop()
routes = web.RouteTableDef()

# Defaults, you can change them if you want
image_w = 120
image_h = 60
timeout = 60 * 5
verify_timeout = 30
gc_sleep = 10

captcha_cache = {}
verify_cache = {}
gc_queue = []

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
            captcha_cache_keys = list(captcha_cache.keys())

            for key in captcha_cache_keys:
                if captcha_cache[key]["solved"]:
                    if run_time > captcha_cache[key]["solved_timestamp"] + verify_timeout:
                        del verify_cache[captcha_cache[key]["verify"]]
                        del captcha_cache[key]
                        count += 1
                elif not captcha_cache[key]["solved"] and run_time > captcha_cache[key]["timestamp"] + timeout:
                    del verify_cache[captcha_cache[key]["verify"]]
                    del captcha_cache[key]
                    count += 1

            for key in gc_queue:
                try:
                    del verify_cache[captcha_cache[key]["verify"]]
                    del captcha_cache[key]
                    gc_queue.remove(key)
                    count += 1
                except:
                    # This should only happen if it was GC'd already
                    gc_queue.remove(key)

            print(f"[Garbage Collector] {len(captcha_cache_keys)} objects in cache, {count} objects collected in this run")
            await asyncio.sleep(gc_sleep)
        except:
            print("[Garbage Collector] Something went wrong while processing the cache")
            await asyncio.sleep(gc_sleep)

@routes.get("/challenge")
async def captcha_challenge(req):
    try:
        scale = int(req.query.get("scale", 1))
        lines = int(req.query.get("lines", 12))
        noise_level = float(req.query.get("noise", 0.25))
        randomize_text_color = True if req.query.get("randomize_text_color", "false") == "true" else False
        randomize_bg_color = True if req.query.get("randomize_bg_color", "true") == "true" else False
    except:
        return web.Response(text="An error occurred while parsing the arguments", status=500, content_type="text/plain")

    if scale > 4 or scale < 1:
        return web.Response(text="\"scale\" should be between 1 and 4", status=500, content_type="text/plain")

    if lines > 32 or lines < 1:
        return web.Response(text="\"lines\" should be between 1 and 32", status=500, content_type="text/plain")

    if noise_level > 1 or noise_level < 0.01:
        return web.Response(text="\"noise\" should be between 0.01 and 1", status=500, content_type="text/plain")

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
    draw.text((text_w, text_h), text, font=text_font, fill=await async_get_random_color() if randomize_text_color else 0)

    # Start applying effects
    noise = Image.fromarray(np.random.randint(0, 255, (image_h * scale, image_w * scale, 3), dtype=np.dtype("uint8")))

    for i in range(0, lines):
        draw.line(await async_get_random_line_pos(scale), fill=0, width=1 * scale)

    image = Image.blend(image, noise, alpha=noise_level)

    bio = BytesIO()
    bio.name = "challenge.jpg"
    image.save(bio)

    captcha_uuid = str(uuid.uuid4())
    verify_uuid = str(uuid.uuid4())

    captcha_cache[captcha_uuid] = {
        "timestamp": time.time(),
        "verify": verify_uuid,
        "image": bio,
        "text": text,
        "solved": False,
        "solved_timestamp": None
    }

    verify_cache[verify_uuid] = captcha_uuid

    return web.json_response({
        "uuid": captcha_uuid,
        "challenge": f"http://localhost:6729/challenge/{captcha_uuid}",
        "submit": f"http://localhost:6729/submit/{captcha_uuid}",
        "verify": f"http://localhost:6729/verify/{verify_uuid}"
    })

@routes.get("/verify/{uuid}")
async def captcha_verify(req):
    verify_uuid = req.match_info["uuid"]
    captcha_uuid = verify_cache.get(verify_uuid)

    if not captcha_uuid:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

    captcha_info = captcha_cache.get(captcha_uuid)

    if captcha_info["solved"]:
        gc_queue.append(captcha_uuid)
        return web.Response(text="Solved", status=200, content_type="text/plain")
    else:
        return web.Response(text="Not solved", status=403, content_type="text/plain")

@routes.get("/submit/{uuid}")
async def captcha_submit(req):
    captcha_uuid = req.match_info["uuid"]
    captcha_info = captcha_cache.get(captcha_uuid)
    text = req.query.get("text")

    if captcha_info:
        if not text:
            return web.Response(text="Incorrect", status=403, content_type="text/plain")
        elif text != captcha_info["text"]:
            return web.Response(text="Incorrect", status=403, content_type="text/plain")
        else:
            captcha_cache[captcha_uuid]["solved"] = True
            captcha_cache[captcha_uuid]["solved_timestamp"] = time.time()
            return web.Response(text="Success", status=200, content_type="text/plain")
    else:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

    return web.Response(text="ACK")

@routes.get("/challenge/{uuid}")
async def captcha_image(req):
    captcha_uuid = req.match_info["uuid"]
    captcha_info = captcha_cache.get(captcha_uuid)

    if captcha_info:
        captcha_info["image"].seek(0)
        return web.Response(body=captcha_info["image"].read(), content_type="image/jpeg", headers={"Content-Disposition": f"inline; filename=\"challenge-{captcha_uuid}.jpg\""})
    else:
        return web.Response(text="The captcha doesnt exist in the cache", status=404, content_type="text/plain")

loop.create_task(garbage_collector_task())

app = web.Application()
app.add_routes(routes)
web.run_app(app, port=6729, loop=loop)
