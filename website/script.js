// Custom Cursor
const cursor = document.querySelector('.cursor');
const cursorFollower = document.querySelector('.cursor-follower');

let mouseX = 0, mouseY = 0;
let cursorX = 0, cursorY = 0;
let followerX = 0, followerY = 0;

document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
});

function animateCursor() {
    cursorX += (mouseX - cursorX) * 0.9;
    cursorY += (mouseY - cursorY) * 0.9;
    followerX += (mouseX - followerX) * 0.5;
    followerY += (mouseY - followerY) * 0.5;

    cursor.style.transform = `translate(${cursorX - 6}px, ${cursorY - 6}px)`;
    cursorFollower.style.transform = `translate(${followerX - 20}px, ${followerY - 20}px)`;

    requestAnimationFrame(animateCursor);
}
animateCursor();

// Hover effects for cursor
document.querySelectorAll('a, button').forEach(el => {
    el.addEventListener('mouseenter', () => {
        cursorFollower.style.width = '60px';
        cursorFollower.style.height = '60px';
        cursorFollower.style.borderColor = 'rgba(0, 255, 136, 0.8)';
    });
    el.addEventListener('mouseleave', () => {
        cursorFollower.style.width = '40px';
        cursorFollower.style.height = '40px';
        cursorFollower.style.borderColor = 'rgba(0, 255, 136, 0.5)';
    });
});

// Particle System
const canvas = document.getElementById('particles');
const ctx = canvas.getContext('2d');

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
resizeCanvas();
window.addEventListener('resize', resizeCanvas);

class Particle {
    constructor() {
        this.reset();
    }

    reset() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2 + 0.5;
        this.speedX = (Math.random() - 0.5) * 0.5;
        this.speedY = (Math.random() - 0.5) * 0.5;
        this.opacity = Math.random() * 0.5 + 0.2;
        this.hue = Math.random() > 0.5 ? 150 : 280;
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;

        if (this.x < 0 || this.x > canvas.width) this.speedX *= -1;
        if (this.y < 0 || this.y > canvas.height) this.speedY *= -1;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${this.hue}, 100%, 70%, ${this.opacity})`;
        ctx.fill();
    }
}

const particles = [];
for (let i = 0; i < 100; i++) {
    particles.push(new Particle());
}

function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach(particle => {
        particle.update();
        particle.draw();
    });

    // Draw connections
    particles.forEach((p1, i) => {
        particles.slice(i + 1).forEach(p2 => {
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < 150) {
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.strokeStyle = `rgba(0, 255, 136, ${0.1 * (1 - distance / 150)})`;
                ctx.lineWidth = 0.5;
                ctx.stroke();
            }
        });
    });

    requestAnimationFrame(animateParticles);
}
animateParticles();

// Counter Animation
const statValues = document.querySelectorAll('.stat-value[data-target]');

const observerOptions = {
    threshold: 0.5,
    rootMargin: '0px'
};

const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const target = parseInt(entry.target.dataset.target);
            animateCounter(entry.target, target);
            counterObserver.unobserve(entry.target);
        }
    });
}, observerOptions);

statValues.forEach(stat => counterObserver.observe(stat));

function animateCounter(element, target) {
    let current = 0;
    const increment = target / 60;
    const duration = 2000;
    const stepTime = duration / 60;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, stepTime);
}

// Smooth Scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Nav Scroll Effect
const nav = document.querySelector('.nav');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 100) {
        nav.style.background = 'rgba(5, 5, 5, 0.95)';
    } else {
        nav.style.background = 'rgba(5, 5, 5, 0.8)';
    }
    
    lastScroll = currentScroll;
});

// Amount Selector
const amountBtns = document.querySelectorAll('.amount-btn');
const estimateValue = document.querySelector('.estimate-value');

amountBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        amountBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const amount = parseInt(btn.dataset.amount);
        const tokens = Math.round(amount / 0.042);
        const bonus = Math.round(tokens * 0.4);
        estimateValue.textContent = `~${tokens.toLocaleString()} $NEXAI + ${bonus.toLocaleString()} bonus`;
    });
});

// Form Submission
const presaleForm = document.getElementById('presale-form');

presaleForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const submitBtn = presaleForm.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    submitBtn.innerHTML = '<span class="btn-text">Processing...</span>';
    submitBtn.disabled = true;
    
    setTimeout(() => {
        submitBtn.innerHTML = '<span class="btn-text">✓ Spot Secured!</span>';
        submitBtn.style.background = 'linear-gradient(135deg, #00ff88, #00cc66)';
        
        setTimeout(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.style.background = '';
            submitBtn.disabled = false;
            presaleForm.reset();
            amountBtns.forEach(b => b.classList.remove('active'));
            amountBtns[1].classList.add('active');
            estimateValue.textContent = '~23,809 $NEXAI + 40% bonus';
        }, 3000);
    }, 1500);
});

// Intersection Observer for fade-in animations
const fadeElements = document.querySelectorAll('.section-header, .feature-card, .timeline-item, .perk');

const fadeObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, { threshold: 0.1 });

fadeElements.forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    fadeObserver.observe(el);
});

// Parallax effect for orbs
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const orbs = document.querySelectorAll('.gradient-orb');
    
    orbs.forEach((orb, index) => {
        const speed = (index + 1) * 0.1;
        orb.style.transform = `translateY(${scrolled * speed}px)`;
    });
});

// Glitch effect on hover
const glitchElement = document.querySelector('.glitch');
if (glitchElement) {
    glitchElement.addEventListener('mouseenter', () => {
        glitchElement.classList.add('glitching');
    });
    glitchElement.addEventListener('mouseleave', () => {
        glitchElement.classList.remove('glitching');
    });
}

// Launch App button effect
const launchBtn = document.getElementById('launch-app');
if (launchBtn) {
    launchBtn.addEventListener('click', () => {
        // Add your app launch logic here
        console.log('Launching app...');
    });
}

console.log('%c NEXUS AI ', 'background: linear-gradient(135deg, #00ff88, #00ccff); color: #000; font-size: 24px; padding: 10px 20px; border-radius: 10px; font-weight: bold;');
console.log('%c The Future Runs on Intelligence ', 'color: #00ff88; font-size: 14px;');
