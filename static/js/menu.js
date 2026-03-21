document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const vegToggle = document.getElementById('vegToggle');
    const menuCards = document.querySelectorAll('.menu-card');

    function filterMenu() {
        const query = searchInput.value.toLowerCase();
        const vegOnly = vegToggle.checked;

        menuCards.forEach(card => {
            const name = card.querySelector('.menu-name').textContent.toLowerCase();
            const desc = card.querySelector('.menu-description').textContent.toLowerCase();
            const isVeg = card.dataset.veg === 'true';

            const matchesSearch = name.includes(query) || desc.includes(query);
            const matchesVeg = vegOnly ? isVeg : true;

            if (matchesSearch && matchesVeg) {
                card.style.display = 'flex';
            } else {
                card.style.display = 'none';
            }
        });
    }

    searchInput.addEventListener('input', filterMenu);
    vegToggle.addEventListener('change', filterMenu);
});
