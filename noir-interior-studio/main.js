/* ==========================================================================
   NOIR INTERIOR STUDIO - INTERACTIVE JAVASCRIPT
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Sticky Navbar background on scroll
  const navbar = document.querySelector('.navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });

  // 2. Consultation Modal Logic
  const modalBackdrop = document.getElementById('consultationModal');
  const openModalBtns = document.querySelectorAll('.open-consultation-modal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const consultationForm = document.getElementById('consultationForm');

  openModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      modalBackdrop.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  });

  const closeModal = () => {
    modalBackdrop.classList.remove('active');
    document.body.style.overflow = '';
  };

  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeModal);
  }

  modalBackdrop.addEventListener('click', (e) => {
    if (e.target === modalBackdrop) {
      closeModal();
    }
  });

  if (consultationForm) {
    consultationForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const btn = consultationForm.querySelector('button[type="submit"]');
      const originalText = btn.textContent;
      btn.textContent = 'REQUEST SENT ✓';
      btn.style.backgroundColor = '#c5a880';
      btn.style.borderColor = '#c5a880';
      btn.style.color = '#000000';

      setTimeout(() => {
        alert('Thank you for contacting Noir Interior Studio. Our design team will reach out to you within 24 hours.');
        closeModal();
        consultationForm.reset();
        btn.textContent = originalText;
        btn.style.backgroundColor = '';
        btn.style.borderColor = '';
        btn.style.color = '';
      }, 800);
    });
  }

  // 3. Testimonials Carousel
  const track = document.getElementById('testimonialTrack');
  const prevBtn = document.getElementById('prevTestimonial');
  const nextBtn = document.getElementById('nextTestimonial');
  let currentIndex = 0;
  const cards = document.querySelectorAll('.testimonial-card');

  const updateCarousel = () => {
    const isMobile = window.innerWidth <= 768;
    const cardWidthPercent = isMobile ? 100 : 33.333;
    const maxIndex = isMobile ? cards.length - 1 : cards.length - 3;
    
    if (currentIndex < 0) currentIndex = 0;
    if (currentIndex > maxIndex) currentIndex = maxIndex;

    const translateValue = -(currentIndex * cardWidthPercent);
    track.style.transform = `translateX(${translateValue}%)`;
  };

  if (prevBtn && nextBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentIndex > 0) {
        currentIndex--;
        updateCarousel();
      }
    });

    nextBtn.addEventListener('click', () => {
      const isMobile = window.innerWidth <= 768;
      const maxIndex = isMobile ? cards.length - 1 : cards.length - 3;
      if (currentIndex < maxIndex) {
        currentIndex++;
        updateCarousel();
      }
    });
  }

  window.addEventListener('resize', updateCarousel);

  // 4. Project Lightbox Modal
  const lightbox = document.getElementById('projectLightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxTitle = document.getElementById('lightboxTitle');
  const lightboxCategory = document.getElementById('lightboxCategory');
  const lightboxDesc = document.getElementById('lightboxDesc');
  const closeLightboxBtn = document.getElementById('closeLightboxBtn');

  const projectCards = document.querySelectorAll('.project-card');
  const projectDetails = {
    ravenwood: {
      title: "Ravenwood Residence",
      category: "LUXURY RESIDENTIAL",
      image: "assets/images/project_ravenwood.jpg",
      desc: "A sprawling private estate in Aspen featuring custom dark oak millwork, leather quartzite stone countertops, and mood lighting designed for ultimate solace and entertaining."
    },
    stratus: {
      title: "Stratus Penthouse",
      category: "URBAN LIVING",
      image: "assets/images/project_stratus.jpg",
      desc: "Perched high above Manhattan, this penthouse merges dark Nero Marquina marble, bronze accents, and minimal sleek lines for sophisticated skyline living."
    },
    obsidian: {
      title: "Obsidian Retreat",
      category: "PRIVATE RESIDENCE",
      image: "assets/images/project_obsidian.jpg",
      desc: "A spa-inspired residential sanctuary centered around raw obsidian stone textures, warm backlit ambient mirrors, and custom charcoal bathtubs."
    },
    eclipse: {
      title: "Eclipse Villa",
      category: "HOSPITALITY DESIGN",
      image: "assets/images/project_eclipse.jpg",
      desc: "Bespoke interior design for a private boutique resort in Santorini, combining micro-cement walls, linear hearth fireplaces, and raw dark minimalist luxury."
    }
  };

  projectCards.forEach(card => {
    card.addEventListener('click', () => {
      const projectId = card.dataset.project;
      const data = projectDetails[projectId];
      if (data && lightbox) {
        lightboxImg.src = data.image;
        lightboxTitle.textContent = data.title;
        lightboxCategory.textContent = data.category;
        lightboxDesc.textContent = data.desc;
        lightbox.classList.add('active');
        document.body.style.overflow = 'hidden';
      }
    });
  });

  if (closeLightboxBtn) {
    closeLightboxBtn.addEventListener('click', () => {
      lightbox.classList.remove('active');
      document.body.style.overflow = '';
    });
  }

  if (lightbox) {
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox) {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  }
});
