const searchInput = document.querySelector("#story-search");
const storyCards = [...document.querySelectorAll(".library-card")];
const emptyMessage = document.querySelector(".empty-search");
const searchStatus = document.querySelector("#search-status");

searchInput?.addEventListener("input", () => {
  const query = searchInput.value.trim().toLocaleLowerCase();
  let visibleCount = 0;

  storyCards.forEach((card) => {
    const matches = !query || card.dataset.search.includes(query);
    card.hidden = !matches;
    if (matches) visibleCount += 1;
  });

  emptyMessage.hidden = visibleCount > 0;
  searchStatus.textContent = `${visibleCount} ${visibleCount === 1 ? "story" : "stories"} found`;
});
