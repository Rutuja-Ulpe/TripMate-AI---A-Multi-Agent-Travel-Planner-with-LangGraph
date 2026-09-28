/* =========================================================
   GLOBAL VARIABLES
========================================================= */

let currentThreadId =
    localStorage.getItem("travel_thread_id") || null;

let latestAnswerMarkdown = "";


/* =========================================================
   QUICK PROMPT
========================================================= */

function setPrompt(text) {

    const input =
        document.getElementById("userInput");

    if (input) {
        input.value = text;
        input.focus();
    }
}


/* =========================================================
   LOADING
========================================================= */

function setLoading(isLoading) {

    const sendBtn =
        document.getElementById("sendBtn");

    const btnText =
        document.getElementById("btnText");

    const btnLoader =
        document.getElementById("btnLoader");

    const loading =
        document.getElementById("loading");


    if (sendBtn) {
        sendBtn.disabled = isLoading;
    }


    if (isLoading) {

        if (btnText) {
            btnText.classList.add("hidden");
        }

        if (btnLoader) {
            btnLoader.classList.remove("hidden");
        }

        if (loading) {
            loading.classList.remove("hidden");
        }

    } else {

        if (btnText) {
            btnText.classList.remove("hidden");
        }

        if (btnLoader) {
            btnLoader.classList.add("hidden");
        }

        if (loading) {
            loading.classList.add("hidden");
        }
    }
}


/* =========================================================
   ERROR
========================================================= */

function showError(message) {

    const errorBox =
        document.getElementById("errorBox");

    if (!errorBox) {
        return;
    }

    errorBox.textContent = message;

    errorBox.classList.remove("hidden");
}


function hideError() {

    const errorBox =
        document.getElementById("errorBox");

    if (!errorBox) {
        return;
    }

    errorBox.textContent = "";

    errorBox.classList.add("hidden");
}


/* =========================================================
   SHOW RESULT
========================================================= */

function showResult(answer, threadId) {

    latestAnswerMarkdown =
        answer || "";


    const resultSection =
        document.getElementById("resultSection");

    const resultBox =
        document.getElementById("resultBox");

    const threadInfo =
        document.getElementById("threadInfo");


    if (!resultSection || !resultBox) {
        return;
    }


    /*
       Convert Markdown response to HTML
    */

    if (
        typeof marked !== "undefined" &&
        answer
    ) {

        resultBox.innerHTML =
            marked.parse(answer);

    } else {

        resultBox.innerText =
            answer || "No response received.";
    }


    /*
       Show Thread ID
    */

    if (threadInfo) {

        threadInfo.textContent =
            `Thread ID: ${threadId}`;
    }


    /*
       Show result section
    */

    resultSection.classList.remove(
        "hidden"
    );


    /*
       Scroll to result
    */

    setTimeout(() => {

        resultSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    }, 100);
}


/* =========================================================
   SEND MESSAGE
========================================================= */

async function sendMessage() {

    hideError();


    const input =
        document.getElementById("userInput");


    if (!input) {

        showError(
            "Input field not found."
        );

        return;
    }


    const message =
        input.value.trim();


    /*
       Validate
    */

    if (!message) {

        showError(
            "Please enter your travel request first."
        );

        return;
    }


    /*
       Start loading
    */

    setLoading(true);


    try {

        console.log(
            "================================="
        );

        console.log(
            "Sending travel request..."
        );

        console.log(
            "Message:",
            message
        );

        console.log(
            "Thread ID:",
            currentThreadId
        );


        /*
           Send request to FastAPI
        */

        const response =
            await fetch(
                "/api/travel",
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        message:
                            message,

                        thread_id:
                            currentThreadId
                    })
                }
            );


        /*
           Read response as text first.
           This makes backend errors easier
           to debug.
        */

        const responseText =
            await response.text();


        console.log(
            "API Status:",
            response.status
        );


        console.log(
            "API Response:",
            responseText
        );


        /*
           Convert response to JSON
        */

        let data;


        try {

            data =
                JSON.parse(
                    responseText
                );

        } catch (parseError) {

            throw new Error(
                "Server returned invalid JSON response: " +
                responseText
            );
        }


        /*
           Backend error
        */

        if (
            !response.ok ||
            !data.success
        ) {

            throw new Error(
                data.error ||
                `Travel API failed with status ${response.status}`
            );
        }


        /*
           Successful response
        */

        console.log(
            "Travel plan generated successfully."
        );


        /*
           Save thread ID
        */

        currentThreadId =
            data.thread_id;


        localStorage.setItem(
            "travel_thread_id",
            currentThreadId
        );


        /*
           Display result
        */

        showResult(
            data.answer,
            data.thread_id
        );


        console.log(
            "Flight results:",
            data.flight_results
        );


        console.log(
            "Hotel results:",
            data.hotel_results
        );


        console.log(
            "Itinerary:",
            data.itinerary
        );


        console.log(
            "LLM calls:",
            data.llm_calls
        );


    } catch (error) {

        console.error(
            "TRAVEL API ERROR:",
            error
        );


        showError(
            error.message ||
            "Failed to generate travel plan."
        );


    } finally {

        setLoading(false);
    }
}


/* =========================================================
   COPY RESULT
========================================================= */

function copyResult() {

    const resultBox =
        document.getElementById("resultBox");


    if (!resultBox) {

        showError(
            "Result box not found."
        );

        return;
    }


    const text =
        resultBox.innerText.trim();


    if (!text) {

        showError(
            "No travel plan available to copy."
        );

        return;
    }


    /*
       Clipboard API
    */

    navigator.clipboard
        .writeText(text)

        .then(() => {

            const copyBtn =
                document.querySelector(
                    ".copy-btn"
                );


            if (!copyBtn) {
                return;
            }


            const oldText =
                copyBtn.textContent;


            copyBtn.textContent =
                "Copied!";


            setTimeout(() => {

                copyBtn.textContent =
                    oldText;

            }, 1400);

        })

        .catch((error) => {

            console.error(
                "COPY ERROR:",
                error
            );

            showError(
                "Could not copy result."
            );
        });
}


/* =========================================================
   DOWNLOAD PDF
========================================================= */

function downloadPDF() {

    const pdfContent =
        document.getElementById(
            "pdfContent"
        );


    /*
       Check result
    */

    if (
        !latestAnswerMarkdown ||
        !pdfContent
    ) {

        showError(
            "No travel plan available to download."
        );

        return;
    }


    /*
       Check PDF library
    */

    if (
        typeof html2pdf === "undefined"
    ) {

        showError(
            "PDF library is not loaded."
        );

        return;
    }


    const downloadBtn =
        document.querySelector(
            ".download-btn"
        );


    if (!downloadBtn) {

        showError(
            "Download button not found."
        );

        return;
    }


    const oldText =
        downloadBtn.textContent;


    downloadBtn.textContent =
        "Preparing PDF...";


    downloadBtn.disabled =
        true;


    /*
       PDF options
    */

    const options = {

        margin: 0.5,

        filename:
            "ai-travel-plan.pdf",

        image: {

            type: "jpeg",

            quality: 0.98
        },

        html2canvas: {

            scale: 2,

            useCORS: true,

            backgroundColor:
                "#ffffff"
        },

        jsPDF: {

            unit: "in",

            format: "a4",

            orientation:
                "portrait"
        },

        pagebreak: {

            mode: [
                "avoid-all",
                "css",
                "legacy"
            ]
        }
    };


    /*
       Generate PDF
    */

    html2pdf()

        .set(options)

        .from(pdfContent)

        .save()

        .then(() => {

            downloadBtn.textContent =
                oldText;

            downloadBtn.disabled =
                false;

        })

        .catch((error) => {

            console.error(
                "PDF ERROR:",
                error
            );


            downloadBtn.textContent =
                oldText;


            downloadBtn.disabled =
                false;


            showError(
                "Could not download PDF."
            );
        });
}


/* =========================================================
   CTRL + ENTER
========================================================= */

document.addEventListener(
    "keydown",
    function (event) {

        if (
            event.ctrlKey &&
            event.key === "Enter"
        ) {

            event.preventDefault();

            sendMessage();
        }
    }
);