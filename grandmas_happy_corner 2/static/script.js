
const menu = document.getElementById("menu");
const views = document.querySelectorAll(".view");
const choiceButtons = document.querySelectorAll(".choice");

const viewToChoice = {
  jokeView: "joke",
  complimentView: "compliment",
  deleteView: "memory",
  quoteView: "quote"
};

const choiceToView = {
  joke: "jokeView",
  compliment: "complimentView",
  memory: "deleteView",
  quote: "quoteView"
};

let appStatus = {
  test_mode: Boolean(window.GRANDMA_APP && window.GRANDMA_APP.testMode),
  choice: "",
  result: null
};

function refreshLocks() {
  choiceButtons.forEach(button => {
    const choice = viewToChoice[button.dataset.view];
    const locked = !appStatus.test_mode && appStatus.choice && appStatus.choice !== choice;

    button.disabled = Boolean(locked);
    button.classList.toggle("locked", Boolean(locked));

    let badge = button.querySelector(".used-today");
    if (locked && !badge) {
      badge = document.createElement("strong");
      badge.className = "used-today";
      badge.textContent = "Tomorrow";
      button.appendChild(badge);
    } else if (!locked && badge) {
      badge.remove();
    }

    let selected = button.querySelector(".today-choice");
    if (appStatus.choice === choice && !selected) {
      selected = document.createElement("strong");
      selected.className = "today-choice";
      selected.textContent = "Today’s choice";
      button.appendChild(selected);
    } else if (appStatus.choice !== choice && selected) {
      selected.remove();
    }
  });

  if (appStatus.test_mode) {
    document.getElementById("testModeNote").classList.remove("hidden");
  }
}

function showOnly(viewId) {
  menu.classList.add("hidden");
  views.forEach(view => view.classList.toggle("hidden", view.id !== viewId));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showMenu() {
  views.forEach(view => view.classList.add("hidden"));
  menu.classList.remove("hidden");
  refreshLocks();
}

document.querySelectorAll(".back").forEach(button => {
  button.addEventListener("click", showMenu);
});

async function loadStatus() {
  const response = await fetch("/api/status");
  if (!response.ok) throw new Error("Could not load daily status.");
  appStatus = await response.json();
  refreshLocks();
}

async function loadCounts() {
  try {
    const response = await fetch("/api/counts");
    const counts = await response.json();
    document.getElementById("collectionCounts").textContent =
      `${counts.jokes} jokes, ${counts.compliments} compliments, and ${counts.quotes} quotes.`;
  } catch {
    document.getElementById("collectionCounts").textContent = "";
  }
}

async function chooseCategory(choice) {
  const response = await fetch("/api/choose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "That choice could not be opened.");
  }

  appStatus.choice = data.choice;
  appStatus.result = data.result;
  refreshLocks();
  return data.result;
}

function renderResult(choice, result) {
  if (choice === "joke") {
    document.getElementById("jokeText").textContent = result.setup;
    document.getElementById("punchlineText").textContent = result.punchline;
    document.getElementById("punchlineText").classList.add("hidden");
    document.getElementById("newJoke").classList.add("hidden");
    document.getElementById("showPunchline").classList.remove("hidden");
  } else if (choice === "compliment") {
    document.getElementById("complimentText").textContent = result.text;
    document.getElementById("newCompliment").classList.add("hidden");
  } else if (choice === "quote") {
    document.getElementById("quoteText").textContent = `“${result.quote}”`;
    document.getElementById("quoteAuthor").textContent = `— ${result.author}`;
    document.getElementById("newQuote").classList.add("hidden");
  } else if (choice === "memory") {
    document.getElementById("fakeDeleteButton").classList.add("hidden");
    document.getElementById("memoryReveal").classList.remove("hidden");
    const photo = document.getElementById("memoryPhoto");
    photo.src = result.url;
    photo.alt = result.name || "A family memory";
    photo.classList.remove("hidden");
  }
}

choiceButtons.forEach(button => {
  button.addEventListener("click", async () => {
    const choice = viewToChoice[button.dataset.view];

    if (!appStatus.test_mode && appStatus.choice && appStatus.choice !== choice) {
      return;
    }

    showOnly(button.dataset.view);

    if (appStatus.choice === choice && appStatus.result) {
      renderResult(choice, appStatus.result);
    }
  });
});

document.getElementById("newJoke").addEventListener("click", async () => {
  const target = document.getElementById("jokeText");
  target.textContent = "Finding a good one…";
  try {
    const result = await chooseCategory("joke");
    renderResult("joke", result);
  } catch (error) {
    target.textContent = error.message;
  }
});

document.getElementById("showPunchline").addEventListener("click", () => {
  document.getElementById("punchlineText").classList.remove("hidden");
  document.getElementById("showPunchline").classList.add("hidden");
});

document.getElementById("newCompliment").addEventListener("click", async () => {
  const target = document.getElementById("complimentText");
  target.textContent = "One moment…";
  try {
    const result = await chooseCategory("compliment");
    renderResult("compliment", result);
  } catch (error) {
    target.textContent = error.message;
  }
});

document.getElementById("newQuote").addEventListener("click", async () => {
  const target = document.getElementById("quoteText");
  target.textContent = "Finding wisdom…";
  try {
    const result = await chooseCategory("quote");
    renderResult("quote", result);
  } catch (error) {
    target.textContent = error.message;
  }
});

document.getElementById("fakeDeleteButton").addEventListener("click", async () => {
  const reveal = document.getElementById("memoryReveal");
  const empty = document.getElementById("memoryEmpty");

  document.getElementById("fakeDeleteButton").classList.add("hidden");
  reveal.classList.remove("hidden");

  try {
    const result = await chooseCategory("memory");
    renderResult("memory", result);
  } catch (error) {
    empty.textContent = error.message;
    empty.classList.remove("hidden");
  }
});

Promise.all([loadStatus(), loadCounts()]).catch(error => {
  console.error(error);
});
