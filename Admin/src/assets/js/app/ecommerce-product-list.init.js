/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Email init js
*/

document.addEventListener('DOMContentLoaded', function () {
  let categoryChoice = document.getElementById('category-choice');
  if (categoryChoice) {
    const choices = new Choices('#category-choice', {
      placeholderValue: 'Select options',
      searchPlaceholderValue: 'Search...',
      removeItemButton: true,
      itemSelectText: 'Press to select',
    });
  }
  let stockChoice = document.getElementById('stock-choice');
  if (stockChoice) {
    const choices = new Choices('#stock-choice', {
      placeholderValue: 'Select options',
      searchPlaceholderValue: 'Search...',
      removeItemButton: true,
      itemSelectText: 'Press to select',
    });
  }
  let productCategoryChoice = document.getElementById('product-category-choice');
  if (productCategoryChoice) {
    const choices = new Choices('#product-category-choice', {
      placeholderValue: 'Select options',
      searchPlaceholderValue: 'Search...',
      removeItemButton: true,
      itemSelectText: 'Press to select',
    });
  }
  let productStockChoice = document.getElementById('product-stock-choice');
  if (productStockChoice) {
    const choices = new Choices('#product-stock-choice', {
      placeholderValue: 'Select options',
      searchPlaceholderValue: 'Search...',
      removeItemButton: true,
      itemSelectText: 'Press to select',
    });
  }
});


// Filter Table Logic
document.addEventListener('DOMContentLoaded', function () {
  const categorySelect = document.getElementById('category-choice');
  const stockSelect = document.getElementById('stock-choice');
  const minPriceInput = document.getElementById('min_price');
  const maxPriceInput = document.getElementById('max_price');
  const searchInput = document.getElementById('search-input');
  const rows = document.querySelectorAll('table tbody tr');

  function normalize(text) {
    return text.toLowerCase().replace(/\s+/g, '').trim();
  }

  function filterTable() {
    const selectedCategory = normalize(categorySelect.value);
    const selectedStock = stockSelect.value.toLowerCase();
    const minPrice = parseFloat(minPriceInput.value);
    const maxPrice = parseFloat(maxPriceInput.value);
    const searchQuery = searchInput ? normalize(searchInput.value) : '';

    rows.forEach(row => {
      const name = normalize(row.children[0]?.textContent || '');
      const category = normalize(row.children[1]?.textContent || '');
      const priceText = row.children[2]?.textContent.replace('$', '') || '0';
      const price = parseFloat(priceText) || 0;
      const stockStatus = normalize(row.children[3]?.textContent || '');

      let visible = true;

      // Category filter
      if (selectedCategory !== 'all' && selectedCategory && !category.includes(selectedCategory)) {
        visible = false;
      }

      // Stock status filter
      if (selectedStock === 'in_stock' && !stockStatus.includes('instock')) {
        visible = false;
      }
      if (selectedStock === 'out_of_stock' && !stockStatus.includes('outofstock')) {
        visible = false;
      }

      // Price filter
      if (!isNaN(minPrice) && price < minPrice) {
        visible = false;
      }
      if (!isNaN(maxPrice) && price > maxPrice) {
        visible = false;
      }

      // Search filter
      if (searchQuery && !name.includes(searchQuery)) {
        visible = false;
      }

      row.style.display = visible ? '' : 'none';
    });
  }

  // Event listeners
  categorySelect?.addEventListener('change', filterTable);
  stockSelect?.addEventListener('change', filterTable);
  minPriceInput?.addEventListener('input', filterTable);
  maxPriceInput?.addEventListener('input', filterTable);
  searchInput?.addEventListener('input', filterTable);

  // Initial filter to apply on page load
  filterTable();
});
