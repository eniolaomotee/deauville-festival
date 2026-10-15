# Reads the data of the festival and prints its name.
# Run it from this folder: uv run main.py
#
# The three lines below open the file and turn its JSON text into Python
# dicts and lists. How they work is explained in step 05; for now, use them.

import json

with open("data/festival.json", encoding="utf-8") as file:
    festival = json.load(file)  

print(festival["name"])
print(f"From {festival['first_day']} to {festival['last_day']}")
print(f"{len(festival['venues'])} venues, {len(festival['artists'])} artists, {len(festival['performances'])} performances")

venues = festival["venues"]
for venue in venues:
    print(f" - {venue['name']}: {venue['capacity']} seats ({venue['address']})")
print(f"Total : {sum(venue['capacity'] for venue in venues)} seats")

counts = {}
for performance in festival["performances"]:
    kind = performance["kind"]
    counts[kind] = counts.get(kind, 0) + 1
for kind, count in counts.items():
    print(f" {kind}: {count} performances")
    

print()
print("At le-kiosque:")
for performance in festival["performances"]:
    if performance["venue"] == "":
        print(f"- {performance['start']} {performance['title']}")

print()
longest = None
for performance in festival["performances"]:
    if longest is None or performance["duration_minutes"] > longest["duration_minutes"]:
        longest = performance
print(f"Longest: {longest['title']} ({longest['duration_minutes']} min)")


print()
for performance in festival["performances"]:
    if performance["kind"] == "workshop":
        days = performance["start"][:10]
        registered = len(performance["participants"])
        places = performance["max_participants"]
        print(f"{performance['title']} on {days}: {registered}/{places} registered")

appearances = {}
for performance in festival["performances"]:
    kind = performance["kind"]
    if kind == "solo":
        on_stage = [performance["artist"]]
    elif kind == "lineup":
        on_stage = [performance["host"]] + performance["acts"]
    elif kind == "workshop":
        on_stage = [performance["teacher"]]
    for slug in on_stage:
        appearances[slug] = appearances.get(slug, 0) + 1

most = max(appearances.values())
busiest = []
for slug, count in appearances.items():
    if count == most:
        busiest.append(slug)
print()
print(f"On stage {most} times: {', '.join(busiest)}")


print()
print()

# Step 02: The program of the day

# The festival days found from the data (no duplicates)
days = []
for performance in festival["performances"]:
    day = performance["start"][:10]
    if day not in days:
        days.append(day)

# Ask for the day until the user enters a valid one
day = input("Day (YYYY-MM-DD): ").strip()
while day not in days:
    print(f"No performance on {day!r}. Days: {', '.join(days)}")
    day = input("Day (YYYY-MM-DD): ").strip()
    
# A dict {slug.name} built once to show venue names
venue_names = {}
for venue in festival["venues"]:
    slug = venue["name"].lower().replace("é", "e").replace("â", "a").replace(" ", "-")
    venue_names[slug] = venue["name"]
    
print(f"Programme for {day}:")
for performance in festival["performances"]:
    if performance["start"][:10] == day:
        time = performance["start"][11:]
        venue_name = venue_names[performance["venue"]]
        print(f"{time} | {venue_name} | {performance['title']} ({performance['kind']})")
