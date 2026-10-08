const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#site-nav");

menuButton?.addEventListener("click", () => {
  const expanded = menuButton.getAttribute("aria-expanded") === "true";
  menuButton.setAttribute("aria-expanded", String(!expanded));
  navigation?.classList.toggle("is-open", !expanded);
});

navigation?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    menuButton?.setAttribute("aria-expanded", "false");
    navigation.classList.remove("is-open");
  });
});

const quiz = document.querySelector("#daily-quiz");
const quizResult = document.querySelector(".quiz-result");

quiz?.addEventListener("submit", (event) => {
  event.preventDefault();
  const answer = new FormData(quiz).get("answer");

  if (!answer) {
    quizResult.textContent = "Choose an answer first.";
  } else if (answer === "olive") {
    quizResult.textContent = "That’s right—the olive tree became a lasting gift to the city.";
  } else {
    quizResult.textContent = "Not quite. In this telling, Athena offered an olive tree.";
  }
});
