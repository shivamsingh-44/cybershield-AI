from ddgs import DDGS


def search_claim(claim, max_results=5):

    results = []

    # Search using the original claim
    queries = [
        f'"{claim}"',
        claim + " official government",
        claim + " fact check"
    ]

    try:
        with DDGS() as ddgs:

            for query in queries:

                search_results = ddgs.text(
                    query,
                    max_results=max_results
                )

                for item in search_results:

                    url = item.get("href", "")

                    # Avoid duplicate results
                    if not url or any(
                        result["url"] == url
                        for result in results
                    ):
                        continue

                    results.append({
                        "title": item.get(
                            "title", "Untitled"
                        ),
                        "url": url,
                        "snippet": item.get(
                            "body", ""
                        )
                    })

                if len(results) >= max_results:
                    break

    except Exception as error:
        print(f"Search error: {error}")

    return results[:max_results]


def display_results(claim, results):

    print("\n" + "=" * 60)
    print("CYBERSHIELD AI — CLAIM INVESTIGATION")
    print("=" * 60)

    print("\nClaim:")
    print(claim)

    if not results:

        print("\nNo search results were retrieved.")
        print("Try again or check your internet connection.")
        return

    print(f"\nRetrieved sources: {len(results)}")

    for index, result in enumerate(results, start=1):

        print(f"\nSOURCE {index}")
        print("-" * 40)

        print("Title:", result["title"])
        print("URL:", result["url"])
        print("Summary:", result["snippet"])

    print("\n" + "=" * 60)
    print("ASSESSMENT: INCONCLUSIVE")
    print(
        "Search results have been retrieved, but their "
        "evidence has not yet been verified."
    )
    print("=" * 60)


if __name__ == "__main__":

    claim = input(
        "Enter a claim to investigate: "
    ).strip()

    if claim:

        results = search_claim(claim)

        display_results(claim, results)

    else:

        print("Please enter a claim.")