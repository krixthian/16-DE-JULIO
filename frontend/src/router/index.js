import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import api from '../services/api'
import { useUserStore } from '../stores/user'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {path:'/tareas',name:'tareas',component:()=>import('../views/TasksView.vue'),meta:{requiresAuth:true,attendance:true}},
    {path:'/calificaciones',name:'calificaciones',component:()=>import('../views/GradesView.vue'),meta:{requiresAuth:true,attendance:true}},
    {path:'/asistencia',name:'asistencia',component:()=>import('../views/AttendanceView.vue'),meta:{requiresAuth:true,attendance:true}},
    ...['gestiones','cursos','estudiantes','matriculas','materias','asignaciones'].map(section=>({
      path:`/escolar/${section}`, name:section,
      component:()=>import('../views/SchoolView.vue'), props:{section},
      meta:{requiresAuth:true,schoolAdmin:true},
    })),
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('../views/UsersView.vue'),
      meta: { requiresAuth: true }
    }
  ]
})

// Guardián de navegación: forzar login si no hay sesión
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.requiresAuth && token) {
    const store = useUserStore()
    try {
      const { data } = await api.get('/auth/me')
      store.login(data, token)
      if (to.meta.schoolAdmin && !['Admin','Director'].includes(data.rol)) return next('/')
      if (to.meta.attendance && !['Admin','Director','Docente'].includes(data.rol)) return next('/')
      if (to.path === '/users' && data.rol !== 'Admin') return next('/')
      next()
    } catch(e) {
      store.logout()
      next('/login')
    }
  } else if (to.path === '/login' && token) {
    // Si ya tiene sesión y trata de ir al login, enviarlo al home
    next('/')
  } else {
    next()
  }
})

export default router
