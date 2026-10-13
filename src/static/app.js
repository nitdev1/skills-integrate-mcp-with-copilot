document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupContainer = document.getElementById("signup-container");
  const messageDiv = document.getElementById("message");
  const userMenuToggle = document.getElementById("user-menu-toggle");
  const userMenuPanel = document.getElementById("user-menu-panel");
  const loginOpenButton = document.getElementById("login-open");
  const logoutButton = document.getElementById("logout-button");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const teacherStatus = document.getElementById("teacher-status");
  let isTeacher = false;

  function showMessage(text, className) {
    messageDiv.textContent = text;
    messageDiv.className = className;
    messageDiv.classList.remove("hidden");
    setTimeout(() => messageDiv.classList.add("hidden"), 5000);
  }

  async function refreshAuthentication() {
    const response = await fetch("/auth/status");
    if (!response.ok) {
      throw new Error("Unable to check teacher login status");
    }

    const result = await response.json();
    isTeacher = result.authenticated;
    signupContainer.hidden = !isTeacher;
    loginOpenButton.classList.toggle("hidden", isTeacher);
    logoutButton.classList.toggle("hidden", !isTeacher);
    teacherStatus.textContent = isTeacher
      ? `Logged in as ${result.username}`
      : "Students can view activities. Teachers must log in to manage registrations.";
  }

  function createActivityCard(name, details) {
    const activityCard = document.createElement("div");
    activityCard.className = "activity-card";

    const title = document.createElement("h4");
    title.textContent = name;
    activityCard.appendChild(title);

    const description = document.createElement("p");
    description.textContent = details.description;
    activityCard.appendChild(description);

    const schedule = document.createElement("p");
    const scheduleLabel = document.createElement("strong");
    scheduleLabel.textContent = "Schedule: ";
    schedule.append(scheduleLabel, document.createTextNode(details.schedule));
    activityCard.appendChild(schedule);

    const availability = document.createElement("p");
    const availabilityLabel = document.createElement("strong");
    availabilityLabel.textContent = "Availability: ";
    availability.append(
      availabilityLabel,
      document.createTextNode(
        `${details.max_participants - details.participants.length} spots left`
      )
    );
    activityCard.appendChild(availability);

    const participantsContainer = document.createElement("div");
    participantsContainer.className = "participants-container";

    if (details.participants.length > 0) {
      const participantsSection = document.createElement("div");
      participantsSection.className = "participants-section";

      const participantsTitle = document.createElement("h5");
      participantsTitle.textContent = "Participants:";
      participantsSection.appendChild(participantsTitle);

      const participantsList = document.createElement("ul");
      participantsList.className = "participants-list";
      details.participants.forEach((email) => {
        const participant = document.createElement("li");
        const participantEmail = document.createElement("span");
        participantEmail.className = "participant-email";
        participantEmail.textContent = email;
        participant.appendChild(participantEmail);

        if (isTeacher) {
          const unregisterButton = document.createElement("button");
          unregisterButton.className = "delete-btn";
          unregisterButton.type = "button";
          unregisterButton.textContent = "Unregister";
          unregisterButton.dataset.activity = name;
          unregisterButton.dataset.email = email;
          unregisterButton.addEventListener("click", handleUnregister);
          participant.appendChild(unregisterButton);
        }

        participantsList.appendChild(participant);
      });
      participantsSection.appendChild(participantsList);
      participantsContainer.appendChild(participantsSection);
    } else {
      const emptyParticipants = document.createElement("p");
      const emptyMessage = document.createElement("em");
      emptyMessage.textContent = "No participants yet";
      emptyParticipants.appendChild(emptyMessage);
      participantsContainer.appendChild(emptyParticipants);
    }

    activityCard.appendChild(participantsContainer);
    return activityCard;
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error(`Activity request failed (${response.status})`);
      }
      const activities = await response.json();

      activitiesList.replaceChildren();
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      Object.entries(activities).forEach(([name, details]) => {
        activitiesList.appendChild(createActivityCard(name, details));

        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.textContent = "Failed to load activities. Please try again later.";
      console.error("Error fetching activities:", error);
    }
  }

  async function handleUnregister(event) {
    const button = event.currentTarget;
    const activity = button.dataset.activity;
    const email = button.dataset.email;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        { method: "DELETE" }
      );
      const result = await response.json();

      if (!response.ok) {
        showMessage(result.detail || "An error occurred", "error");
        return;
      }

      showMessage(result.message, "success");
      await fetchActivities();
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  userMenuToggle.addEventListener("click", () => {
    const isExpanded = userMenuToggle.getAttribute("aria-expanded") === "true";
    userMenuToggle.setAttribute("aria-expanded", String(!isExpanded));
    userMenuPanel.classList.toggle("hidden", isExpanded);
  });

  loginOpenButton.addEventListener("click", () => {
    userMenuPanel.classList.add("hidden");
    userMenuToggle.setAttribute("aria-expanded", "false");
    loginError.textContent = "";
    loginError.classList.add("hidden");
    loginDialog.showModal();
  });

  document.getElementById("login-cancel").addEventListener("click", () => {
    loginDialog.close();
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      const result = await response.json();

      if (!response.ok) {
        loginError.textContent = result.detail || "Unable to log in.";
        loginError.classList.remove("hidden");
        return;
      }

      loginForm.reset();
      loginDialog.close();
      await refreshAuthentication();
      await fetchActivities();
      showMessage("Teacher login successful.", "success");
    } catch (error) {
      loginError.textContent = "Unable to log in. Please try again.";
      loginError.classList.remove("hidden");
      console.error("Error logging in:", error);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Unable to log out.", "error");
        return;
      }

      userMenuPanel.classList.add("hidden");
      userMenuToggle.setAttribute("aria-expanded", "false");
      await refreshAuthentication();
      await fetchActivities();
      showMessage("Logged out.", "success");
    } catch (error) {
      showMessage("Unable to log out. Please try again.", "error");
      console.error("Error logging out:", error);
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const activity = activitySelect.value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        { method: "POST" }
      );
      const result = await response.json();

      if (!response.ok) {
        showMessage(result.detail || "An error occurred", "error");
        return;
      }

      showMessage(result.message, "success");
      signupForm.reset();
      await fetchActivities();
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  async function initialize() {
    try {
      await refreshAuthentication();
    } catch (error) {
      teacherStatus.textContent = "Unable to check teacher login status.";
      console.error("Error checking teacher login status:", error);
    }
    await fetchActivities();
  }

  initialize();
});
