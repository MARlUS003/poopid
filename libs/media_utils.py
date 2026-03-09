import os
import asyncio
import subprocess
import tempfile
import aiohttp
import discord

async def handle_to_gif(interaction: discord.Interaction, message: discord.Message):
    """Logic for converting a video to an Animated WebP."""
    video_url = None

    video_attachment = next((a for a in message.attachments if a.content_type and "video" in a.content_type), None)
    if video_attachment:
        video_url = video_attachment.url

    if not video_url:
        for embed in message.embeds:
            if embed.video and embed.video.url:
                video_url = embed.video.url
                break

    if not video_url:
        await interaction.response.send_message("use the command on a video, you dumbass", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input_vid")
        output_path = os.path.join(tmpdir, "output.webp")

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        await asyncio.to_thread(lambda: open(input_path, 'wb').write(data))
                    else:
                        await interaction.followup.send("stupid video")
                        return
        except Exception as e:
            await interaction.followup.send(f"Dumbass video wont download: {e}")
            return

        try:
            def run_ffmpeg_webp(scale_str, q_val):
                subprocess.run([
                    "ffmpeg", "-i", input_path,
                    "-vcodec", "libwebp",
                    "-filter_complex", f"fps=30,scale={scale_str}:flags=lanczos",
                    "-lossless", "0",
                    "-compression_level", "0",
                    "-q:v", str(q_val),
                    "-loop", "0",
                    "-an",
                    "-y", output_path
                ], check=True)

            await asyncio.to_thread(run_ffmpeg_webp, "iw/2:ih/2", 60)

            attempts = 0
            pixel_scale = 480
            quality = 60
            while os.path.exists(output_path) and os.path.getsize(output_path) > 8 * 1024 * 1024 and attempts < 4:
                quality -= 15
                scale_str = f"{pixel_scale}:-1"
                await asyncio.to_thread(run_ffmpeg_webp, scale_str, max(quality, 10))
                pixel_scale = int(pixel_scale * 0.7)
                attempts += 1

            if not os.path.exists(output_path) or os.path.getsize(output_path) > 8 * 1024 * 1024:
                await interaction.followup.send("shit over 8 mb bruh")
                return

            await interaction.followup.send(file=discord.File(output_path, filename="converted.webp"))
        except Exception as e:
            await interaction.followup.send(f"ffmpeg killed itself: {e}")

async def handle_overlay_gif(ctx, gifname: str):
    """Logic for overlaying a local gif onto a message attachment/embed."""
    if not gifname:
        return await ctx.send("You need to specify a gif name! Usage: `-g missile`")

    target_msg = None
    if ctx.message and ctx.message.reference:
        target_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    
    if not target_msg:
        async for m in ctx.channel.history(limit=1):
            target_msg = m

    if not target_msg:
        return await ctx.send("I couldn't find a message to process!")

    # Check for gif inside the 'gifs/' folder
    overlay_asset = os.path.abspath(os.path.join("gifs", f"{gifname}.gif"))
    if not os.path.exists(overlay_asset):
        return await ctx.send(f"No gif named `{gifname}.gif` found in the `gifs/` folder!")

    media_url = None
    if target_msg.attachments:
        att = target_msg.attachments[0]
        if any(att.filename.lower().endswith(e) for e in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            media_url = att.url
    
    if not media_url and target_msg.embeds:
        emb = target_msg.embeds[0]
        target = emb.image or emb.thumbnail
        if target and target.url:
            media_url = target.url

    if not media_url:
        return await ctx.send("I couldn't find an image/gif in that message!")

    ext = ".gif"
    for e in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        if media_url.lower().split('?')[0].endswith(e):
            ext = e
            break

    await ctx.defer()

    # Reimplemented typing indicator for visual feedback during processing
    async with ctx.typing():
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.abspath(os.path.join(tmpdir, f"base_media{ext}"))
            output_path = os.path.abspath(os.path.join(tmpdir, "overlay_output.webp"))

            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(media_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            with open(input_path, 'wb') as f:
                                f.write(data)
                        else:
                            return await ctx.send(f"Download failed: HTTP {resp.status}")
            except Exception as e:
                return await ctx.send(f"Download error: {e}")

            try:
                def get_media_dims(path):
                    cmd = [
                        "ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path
                    ]
                    result = subprocess.check_output(cmd).decode().strip()
                    w, h = map(int, result.split('x'))
                    return w, h

                orig_w, orig_h = await asyncio.to_thread(get_media_dims, input_path)
                if orig_w == 0: orig_w = 1

                current_pixel_scale = 800
                current_quality = 60

                def run_ffmpeg_overlay(scale_val, q_val):
                    is_animated = ext.lower() in ('.gif', '.webp')
                    target_h = int((scale_val / orig_w) * orig_h)
                    
                    filter_str = (
                        f"[1:v]format=rgba,scale={scale_val}:{target_h}:flags=lanczos[base];"
                        f"[2:v]format=rgba,scale={scale_val}:{target_h}:flags=lanczos[ovl];"
                        f"[0:v][base]overlay=format=auto[bg_with_base];"
                        f"[bg_with_base][ovl]overlay=format=auto:shortest=1"
                    )
                    
                    cmd = ["ffmpeg"]
                    cmd += ["-f", "lavfi", "-i", f"color=c=black@0:s={scale_val}x{target_h}"]
                    if ext.lower() == '.webp':
                        cmd += ["-vcodec", "libwebp"]
                    if not is_animated: cmd += ["-loop", "1"]
                    cmd += ["-i", input_path]
                    cmd += ["-i", overlay_asset]
                    if not is_animated: cmd += ["-t", "5"]
                    cmd += [
                        "-vcodec", "libwebp",
                        "-filter_complex", filter_str,
                        "-compression_level", "0",
                        "-q:v", str(q_val),
                        "-loop", "0", "-y", output_path
                    ]
                    subprocess.run(cmd, check=True)

                await asyncio.to_thread(run_ffmpeg_overlay, current_pixel_scale, current_quality)

                attempts = 0
                while os.path.exists(output_path) and os.path.getsize(output_path) > 8 * 1024 * 1024 and attempts < 2:
                    current_quality -= 15
                    current_pixel_scale = int(current_pixel_scale * 0.8)
                    if current_pixel_scale < 200: break
                    await asyncio.to_thread(run_ffmpeg_overlay, current_pixel_scale, max(current_quality, 20))
                    attempts += 1

                if not os.path.exists(output_path) or os.path.getsize(output_path) > 8 * 1024 * 1024:
                    return await ctx.send("File is too chunky.")

                await ctx.send(file=discord.File(output_path, filename=f"{gifname}_overlay.webp"))

            except Exception as e:
                print(f"[Overlay] FFmpeg error: {e}")
                await ctx.send(f"Processing failed: {e}")
