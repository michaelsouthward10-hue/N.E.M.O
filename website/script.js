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
const quizQuestion = document.querySelector("#quiz-question");
const quizProgress = document.querySelector("#quiz-progress");
const quizOptions = quiz?.querySelector("fieldset");
const quizButton = quiz?.querySelector('button[type="submit"]');
const quizResult = document.querySelector(".quiz-result");

const questions = [
  {
    prompt: "According to Apollodorus, what did Athena plant on the Acropolis?",
    answers: ["An olive tree", "A spring of seawater", "A horse"],
    correct: 0,
    note: "Athena planted an olive tree, with Cecrops as witness."
  },
  {
    prompt: "What did Poseidon produce with a blow of his trident?",
    answers: ["A flock of sheep", "A sea or salt-water spring", "A grove of olives"],
    correct: 1,
    note: "In this account Poseidon struck the Acropolis and produced a sea called Erechtheis."
  },
  {
    prompt: "Who witnessed Athena planting the olive tree?",
    answers: ["Cecrops", "Heracles", "Hermes"],
    correct: 0,
    note: "Cecrops, the early king of Attica, witnessed Athena’s act."
  },
  {
    prompt: "Who judged the contest in Apollodorus’s account?",
    answers: ["The people of Troy", "The Twelve Gods", "The Muses"],
    correct: 1,
    note: "Apollodorus says the Twelve Gods served as arbiters."
  },
  {
    prompt: "Why was Attica awarded to Athena in this telling?",
    answers: ["Cecrops testified she planted the olive first", "Poseidon withdrew his claim", "Athena won a footrace"],
    correct: 0,
    note: "Cecrops testified that Athena had planted the olive first. Other tellings differ."
  }
];

let questionIndex = 0;
let score = 0;
let answered = false;

function renderQuestion() {
  const question = questions[questionIndex];
  quizQuestion.textContent = question.prompt;
  quizProgress.textContent = `QUESTION ${questionIndex + 1} OF ${questions.length}`;
  quizOptions.replaceChildren();

  question.answers.forEach((answer, index) => {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "answer";
    input.value = String(index);
    input.required = true;
    label.append(input, document.createTextNode(` ${answer}`));
    quizOptions.append(label);
  });

  quizResult.textContent = "";
  quizButton.innerHTML = 'Check my answer <span aria-hidden="true">→</span>';
  answered = false;
}

quiz?.addEventListener("submit", (event) => {
  event.preventDefault();

  if (quizButton.dataset.action === "restart") {
    questionIndex = 0;
    score = 0;
    delete quizButton.dataset.action;
    renderQuestion();
    return;
  }

  if (answered) {
    questionIndex += 1;
    if (questionIndex === questions.length) {
      quizProgress.textContent = "QUIZ COMPLETE";
      quizQuestion.textContent = `You scored ${score} out of ${questions.length}.`;
      quizOptions.replaceChildren();
      quizResult.textContent = score === questions.length
        ? "A perfect journey through this account of the myth."
        : "Every telling leaves something new to discover. Explore the source story to learn more.";
      quizButton.innerHTML = 'Play again <span aria-hidden="true">↻</span>';
      quizButton.dataset.action = "restart";
      answered = false;
      return;
    }
    renderQuestion();
    return;
  }

  const selected = new FormData(quiz).get("answer");
  if (selected === null) {
    quizResult.textContent = "Choose an answer first.";
    return;
  }

  const question = questions[questionIndex];
  const isCorrect = Number(selected) === question.correct;
  if (isCorrect) score += 1;
  quizResult.textContent = `${isCorrect ? "That’s right. " : "Not quite. "}${question.note}`;
  quizButton.innerHTML = questionIndex === questions.length - 1
    ? 'See my result <span aria-hidden="true">→</span>'
    : 'Next question <span aria-hidden="true">→</span>';
  answered = true;
});

if (quiz && quizQuestion && quizProgress && quizOptions && quizButton && quizResult) {
  quiz.addEventListener("reset", () => {
    questionIndex = 0;
    score = 0;
    delete quizButton.dataset.action;
    renderQuestion();
  });
}
