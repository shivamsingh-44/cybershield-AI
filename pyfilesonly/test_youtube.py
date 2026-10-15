from social_media import search_youtube

print("CyberShield AI - YouTube Connection Test")

query = input("Enter a topic to search: ").strip()

if query:
    result = search_youtube(query)

    if result.get("error"):
        print("\nError:", result["error"])
    else:
        videos = result["videos"]
        print(f"\nVideos found: {len(videos)}")

        for video in videos:
            print("\nTitle:", video["title"])
            print("Channel:", video["channel"])
            print("Published:", video["published_at"])
            print("URL:", video["url"])
else:
    print("Please enter a topic.")