document.addEventListener("DOMContentLoaded", () => {
    console.log("IITconnect.vk loaded!")
  
    // Password validation
    const passwordForm = document.getElementById("signup-form")
    if (passwordForm) {
      passwordForm.addEventListener("submit", (event) => {
        const password = document.getElementById("password").value
        const confirmPassword = document.getElementById("confirm_password").value
  
        if (password !== confirmPassword) {
          event.preventDefault()
          alert("Passwords do not match!")
        }
      })
    }
  
    // Password visibility toggle
    const passwordToggles = document.querySelectorAll(".password-toggle")
    passwordToggles.forEach((toggle) => {
      toggle.addEventListener("click", function () {
        const targetId = this.getAttribute("data-target")
        const passwordInput = document.getElementById(targetId)
        const icon = this.querySelector("i")
  
        if (passwordInput.type === "password") {
          passwordInput.type = "text"
          icon.classList.remove("fa-eye")
          icon.classList.add("fa-eye-slash")
        } else {
          passwordInput.type = "password"
          icon.classList.remove("fa-eye-slash")
          icon.classList.add("fa-eye")
        }
      })
    })
  })
  
  