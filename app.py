from flask import Flask, render_template, request, redirect, session, url_for
import pandas as pd
import difflib
import random
import requests
from difflib import get_close_matches

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

TMDB_API_KEY = "168ffc7714864158900c1a876ca1ad77"
TMDB_HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxNjhmZmM3NzE0ODY0MTU4OTAwYzFhODc2Y2ExYWQ3NyIsIm5iZiI6MTc0NzY4NzE2MC41MTAwMDAyLCJzdWIiOiI2ODJiOTZmOGE1OGM1MDk4NTMyZjc3MmIiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.Qgi1VNdLBbJuovtARtUvljn_JHIBNF1bpZztG_1IjmM"
}

# Load movie data once
def load_movies():
    df = pd.read_csv("movie_info.csv", on_bad_lines="skip")
    df = df.dropna(subset=["critic_score", "audience_score", "release_date"])

    # Remove '%' and lowercase text to detect invalid scores like 'n/a'
    df["critic_score"] = df["critic_score"].astype(str).str.strip().str.lower()
    df["audience_score"] = df["audience_score"].astype(str).str.strip().str.lower()

    # Filter out rows with non-numeric scores (e.g., 'n/a', 'unrated')
    df = df[df["critic_score"].str.match(r"^\d+%$")]
    df = df[df["audience_score"].str.match(r"^\d+%$")]

    # Now strip % and convert to int
    df["critic_score"] = df["critic_score"].str.rstrip('%').astype(int)
    df["audience_score"] = df["audience_score"].str.rstrip('%').astype(int)

    # Extract year from release_date (handles 'Released Mar 3, 1995' or just '1995')
    df["release_year"] = df["release_date"].str.extract(r"(\d{4})")
    df = df.dropna(subset=["release_year"])
    df["release_year"] = df["release_year"].astype(int)

    return df

df = load_movies()

def get_tmdb_poster_url(title, year=None):
    params = {
        "query": title,
        "include_adult": "false"
    }
    if year:
        params["year"] = year

    search_url = "https://api.themoviedb.org/3/search/movie"
    try:
        response = requests.get(search_url, headers=TMDB_HEADERS, params=params)
        data = response.json()
        results = data.get("results", [])

        print(f"TMDb results for '{title}': {[r['title'] for r in results if 'title' in r]}")

        titles = [r.get("title", "") for r in results]
        close = get_close_matches(title, titles, n=1, cutoff=0.6)

        if close:
            match = next((r for r in results if r.get("title") == close[0]), None)
            if match and match.get("poster_path"):
                poster_path = match["poster_path"]
                return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"TMDb fetch error for '{title}': {e}")

    return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        players = [name for name in request.form.getlist("player") if name.strip()]
        game_type = request.form.get("gameType")
        selected_decade = request.form.get("decade")

        session["players"] = players
        session["scores"] = {name: 0 for name in players}
        session["round"] = 1
        session["guesses"] = {}
        session["movie"] = None
        session["game_type"] = game_type
        session["selected_decade"] = int(selected_decade) if selected_decade else None

        if game_type == "custom":
            custom_titles = [title.strip() for title in request.form.getlist("custom_movie") if title.strip()]
            session["custom_titles"] = custom_titles[:5]
        else:
            session["custom_titles"] = None

        return redirect(url_for("game"))


    movie_list = df[["title", "release_year"]].dropna().to_dict(orient="records")
    return render_template("index.html", movie_titles=movie_list)


@app.route("/game", methods=["GET", "POST"])
def game():
    if "round" not in session or session["round"] > 5:
        return redirect(url_for("results"))

    if request.method == "POST":
        guesses = {}
        for player in session["players"]:
            guess = int(request.form[player])
            guesses[player] = guess

        session["last_guesses"] = guesses
        return redirect(url_for("round_result"))
    
    if session["custom_titles"]:
        title = session["custom_titles"][session["round"] - 1]
        
        # Fuzzy match against known titles
        all_titles = df["title"].str.lower().tolist()
        close_matches = difflib.get_close_matches(title.lower(), all_titles, n=1, cutoff=0.6)

        if not close_matches:
            return f"Could not find a close match for '{title}'. Please check spelling.", 400

        match_title = close_matches[0]
        movie = df[df["title"].str.lower() == match_title].head(1).iloc[0]
    else:
        selected_decade = session.get("selected_decade")
        filtered_df = df

        if selected_decade:
            filtered_df = df[(df["release_year"] >= selected_decade) & (df["release_year"] < selected_decade + 10)]

        movie = filtered_df.sample(1).iloc[0]
        
    # Fetch poster from TMDb using title and release year
    poster_url = get_tmdb_poster_url(movie["title"], movie["release_year"])
    print(f"✔️ Poster for '{movie['title']}': {poster_url}")

    # Store movie details in session
    session["movie"] = {
        "title": f"{movie['title']} ({movie['release_year']})",
        "critic_score": int(movie["critic_score"]),
        "audience_score": int(movie["audience_score"]),
        "poster_url": poster_url
    }

    return render_template("game.html", round_num=session["round"], players=session["players"], movie=session["movie"]["title"])

@app.route("/round_result", methods=["GET", "POST"])
def round_result():
    if request.method == "POST":
        actual_score = session["movie"]["critic_score"]
        guesses = session["last_guesses"]
        scores = session["scores"]

        for player in session["players"]:
            guess = guesses[player]
            if guess == actual_score:
                # Bonus for perfect guess
                scores[player] -= 10
            else:
                diff = abs(guess - actual_score)
                scores[player] += diff

        session["scores"] = scores
        session["round"] += 1
        return redirect(url_for("game" if session["round"] <= 5 else "results"))

    return render_template(
        "round_result.html",
        movie=session["movie"]["title"],
        actual=session["movie"]["critic_score"],
        audience=session["movie"].get("audience_score"),
        guesses=session["last_guesses"],
        scores=session["scores"]
    )



@app.route("/results")
def results():
    scores = session.get("scores", {})
    sorted_scores = sorted(scores.items(), key=lambda x: x[1])
    return render_template("results.html", scores=sorted_scores)

if __name__ == "__main__":
    app.run(debug=True)
