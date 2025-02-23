document.addEventListener("DOMContentLoaded", () => {
  // For demo, default user id is assumed to be 1 (for claim/continue saving endpoints)
  const userId = 1;

  // --- Expense Processing from Search Container ---
  const searchButton = document.querySelector(".search-button");
  const searchBar = document.querySelector(".search-bar");

  searchButton.addEventListener("click", async (e) => {
    e.preventDefault();
    
    const inputValue = searchBar.value.trim(); // Expected: "2-22-2025, Food, 25.5"
    const parts = inputValue.split(",");
    
    if (parts.length !== 3) {
      alert("Invalid format. Please use: 2-22-2025, Food, 25.5");
      return;
    }
    
    let datePart = parts[0].trim(); // e.g., "2-22-2025"
    const typePart = parts[1].trim(); // e.g., "Food"
    const amountPart = parts[2].trim(); // e.g., "25.5"
    
    // Reformat datePart "2-22-2025" to "YYYY-MM-DD"
    let [month, day, year] = datePart.split("-");
    if (!year || !month || !day) {
      alert("Invalid date format. Use: 2-22-2025");
      return;
    }
    if (month.length === 1) month = "0" + month;
    if (day.length === 1) day = "0" + day;
    const formattedDate = `${year}-${month}-${day}`;

    // Parse the amount (remove any "$" sign if present)
    const originalAmount = parseFloat(amountPart.replace("$", ""));
    if (isNaN(originalAmount)) {
      alert("Invalid amount. Please provide a valid number.");
      return;
    }
    
    // Construct payload (no user_id required; backend uses default demo user)
    const payload = {
      expense_date: formattedDate,
      expense_type: typePart,
      amount: originalAmount
    };
    
    try {
      const response = await fetch("http://127.0.0.1:8000/transactions/calc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || response.statusText);
      }
      
      const result = await response.json();
      
      // Insert a new row in the transactions table
      const transactionsTable = document.getElementById("transactions-table");
      const newRow = document.createElement("tr");

      const dateCell = document.createElement("td");
      dateCell.innerText = result.expense_date;

      const descCell = document.createElement("td");
      descCell.innerText = result.expense_type;

      const amountCell = document.createElement("td");
      amountCell.innerText = `$${result.final_charge.toFixed(2)}`;
      if (result.charge_type === "fake") {
        amountCell.classList.add("negative");
      }

      // Show updated balance in the new row
      const balanceCell = document.createElement("td");
      balanceCell.innerText = `$${result.new_current_balance.toFixed(2)}`;

      newRow.appendChild(dateCell);
      newRow.appendChild(descCell);
      newRow.appendChild(amountCell);
      newRow.appendChild(balanceCell);

      transactionsTable.appendChild(newRow);
      
      // Update main balance display on the page
      const currentBalanceElement = document.getElementById("current-balance");
      if (currentBalanceElement) {
        currentBalanceElement.innerText = `$${result.new_current_balance.toFixed(2)}`;
      }
      
      // Update ghost budget display
      const ghostBudgetElement = document.getElementById("ghost-budget");
      if (ghostBudgetElement && result.new_ghost_budget !== undefined) {
        ghostBudgetElement.innerText = `$${result.new_ghost_budget.toFixed(2)}`;
      }
      
      // Clear the search input
      searchBar.value = "";
    } catch (error) {
      console.error("Error processing expense:", error);
      alert("Error: " + (error.message || JSON.stringify(error)));
    }
  });

  // --- Claim Button ---
  const claimButton = document.getElementById("claim-btn");
  claimButton.addEventListener("click", async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/users/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId })
      });
      if (!response.ok) {
        throw new Error("Error claiming ghost budget");
      }
      const data = await response.json();
      alert(data.message);
      // Update current balance and ghost budget in the DOM
      document.getElementById("current-balance").innerText = `$${data.current_balance.toFixed(2)}`;
      document.getElementById("ghost-budget").innerText = `$${data.new_ghost_budget.toFixed(2)}`;
    } catch (error) {
      console.error(error);
      alert("Error: " + (error.message || JSON.stringify(error)));
    }
  });

  // --- Continue Saving Button ---
  const continueButton = document.getElementById("continue-saving-btn");
  continueButton.addEventListener("click", async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/users/continue-saving", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId })
      });
      if (!response.ok) {
        throw new Error("Error continuing saving");
      }
      const data = await response.json();
      alert(data.message);
      // Update Roth IRA, High Yield Savings, and ghost budget in the DOM
      document.getElementById("roth-ira").innerText = `$${data.roth_ira_contribution.toFixed(2)}`;
      document.getElementById("high-yield").innerText = `$${data.high_yield_savings.toFixed(2)}`;
      document.getElementById("ghost-budget").innerText = `$${data.new_ghost_budget.toFixed(2)}`;
    } catch (error) {
      console.error(error);
      alert("Error: " + (error.message || JSON.stringify(error)));
    }
  });
});
