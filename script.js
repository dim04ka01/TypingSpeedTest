document.addEventListener('DOMContentLoaded', () => {
    const typingArea = document.getElementById('typing-area');
    const textSample = document.getElementById('text-sample');
    const timerDisplay = document.getElementById('timer');
    const wpmDisplay = document.getElementById('wpm');
    const accuracyDisplay = document.getElementById('accuracy');
    const restartBtn = document.getElementById('restart-btn');

    const socket = io();
    let startTime = null;
    let timerInterval = null;
    let originalText = textSample.textContent.trim();
    let charSpans = [];

    // Èíèöèàëèçàöèÿ òåêñòà
    function initText() {
        textSample.innerHTML = '';
        charSpans = [];

        originalText.split('').forEach((char, index) => {
            const span = document.createElement('span');
            span.className = 'char';
            span.textContent = char;
            span.dataset.index = index;
            textSample.appendChild(span);
            charSpans.push(span);
        });

        charSpans[0].classList.add('current');
    }

    initText();
    typingArea.focus();
    initRadioButtons();

    // Îáðàáîò÷èêè ñîáûòèé
    typingArea.addEventListener('input', handleTyping);
    restartBtn.addEventListener('click', resetTest);

    document.getElementById('apply-settings').addEventListener('click', applySettings);

    function applySettings() {
        const textType = document.querySelector('input[name="text-type"]:checked').value;
        const language = document.querySelector('input[name="language"]:checked').value;
        const difficulty = document.querySelector('input[name="difficulty"]:checked').value;

        fetch('/update_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text_type: textType,
                language: language,
                difficulty: difficulty
            })
        })
            .then(response => response.json())
            .then(data => {
                originalText = data.new_text.trim();
                textSample.textContent = originalText;
                initText();
                resetTestState();

                // Ïðèíóäèòåëüíî ïåðåïîäêëþ÷àåì ñîêåò
                socket.disconnect();
                socket.connect();
            });
        document.querySelectorAll('.radio-group label').forEach(label => {
            label.classList.remove('active');
        });

        document.querySelectorAll(`input[name="text-type"]:checked`).forEach(radio => {
            radio.closest('label').classList.add('active');
        });

        document.querySelectorAll(`input[name="language"]:checked`).forEach(radio => {
            radio.closest('label').classList.add('active');
        });

        document.querySelectorAll(`input[name="difficulty"]:checked`).forEach(radio => {
            radio.closest('label').classList.add('active');
        });
    }
    function initRadioButtons() {
        // Äëÿ âñåõ ãðóïï ðàäèî-êíîïîê
        document.querySelectorAll('.radio-group').forEach(group => {
            const radios = group.querySelectorAll('input[type="radio"]');

            radios.forEach(radio => {
                // Îáðàáîò÷èê èçìåíåíèÿ ñîñòîÿíèÿ
                radio.addEventListener('change', function () {
                    // Ñáðàñûâàåì ñòèëè ó âñåõ â ãðóïïå
                    radios.forEach(r => {
                        r.closest('label').classList.remove('active');
                    });

                    // Ïðèìåíÿåì ñòèëü ê âûáðàííîé
                    if (this.checked) {
                        this.closest('label').classList.add('active');
                    }
                });

                // Èíèöèàëèçàöèÿ àêòèâíîãî ñîñòîÿíèÿ ïðè çàãðóçêå
                if (radio.checked) {
                    radio.closest('label').classList.add('active');
                }
            });
        });
    }

    function handleTyping() {
        const typedText = typingArea.value;

        // Çàïóñê òåñòà ïðè ïåðâîì ââîäå
        if (!startTime) {
            startTest();
        }

        // Îáíîâëåíèå ïîäñâåòêè ñèìâîëîâ
        updateCharacterHighlighting(typedText);

        // Îáíîâëåíèå ñòàòèñòèêè
        updateRealtimeStats(typedText);

        // Ïðîâåðêà çàâåðøåíèÿ òåñòà
        if (typedText.length >= originalText.length) {
            finishTest();
        }
    }

    function updateCharacterHighlighting(typedText) {
        charSpans.forEach((span, index) => {
            span.classList.remove('current', 'correct', 'incorrect');

            if (index < typedText.length) {
                if (typedText[index] === originalText[index]) {
                    span.classList.add('correct');
                } else {
                    span.classList.add('incorrect');
                }
            }

            if (index === typedText.length) {
                span.classList.add('current');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Àâòîìàòè÷åñêàÿ ïðîêðóòêà ê ïåðâîé îøèáêå
        const firstMistake = document.querySelector('.char.mistake');
        if (firstMistake) {
            firstMistake.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'center'
            });

            // Ïîäñâåòêà ïåðâîé îøèáêè
            firstMistake.classList.add('highlight');
            setTimeout(() => {
                firstMistake.classList.remove('highlight');
            }, 2000);
        }
    });

    function startTest() {
        startTime = new Date().getTime();
        socket.emit('start_test');

        timerInterval = setInterval(() => {
            const elapsed = Math.floor((new Date().getTime() - startTime) / 1000);
            const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            timerDisplay.textContent = `${minutes}:${seconds}`;
        }, 1000);
    }

    function updateRealtimeStats(typedText) {
        const elapsed = (new Date().getTime() - startTime) / 1000 / 60; // â ìèíóòàõ
        const typedWords = typedText.trim().split(/\s+/).length;

        if (elapsed > 0) {
            const wpm = Math.round(typedWords / elapsed);
            wpmDisplay.textContent = wpm;
        }

        // Ðàñ÷åò òî÷íîñòè
        let correctChars = 0;
        for (let i = 0; i < Math.min(typedText.length, originalText.length); i++) {
            if (typedText[i] === originalText[i]) correctChars++;
        }

        const accuracy = originalText.length > 0
            ? Math.round((correctChars / originalText.length) * 100)
            : 100;
        accuracyDisplay.textContent = `${accuracy}%`;
    }

    function finishTest() {
        clearInterval(timerInterval);
        typingArea.disabled = true;

        socket.emit('submit_results', {
            typed_text: typingArea.value
        });

        // Îáðàáîòêà ðåçóëüòàòîâ è ïåðåõîä íà ñòðàíèöó ðåçóëüòàòîâ
        socket.on('test_results', (data) => {
            if (data.test_id) {
                // Ïåðåõîäèì íà ñòðàíèöó ðåçóëüòàòîâ ñ ïàðàìåòðîì test_id
                window.location.href = `/results?test_id=${data.test_id}`;
            } else {
                console.error("Test ID not received");
                window.location.href = '/';
            }
        });
    }

    function resetTest() {
        clearInterval(timerInterval);
        startTime = null;
        typingArea.value = '';
        typingArea.disabled = false;
        timerDisplay.textContent = '00:00';
        wpmDisplay.textContent = '0';
        accuracyDisplay.textContent = '100%';
        window.location.reload();
    }

    socket.on('disconnect', () => {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        startTime = null;
    });
});
