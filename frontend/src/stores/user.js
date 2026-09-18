import { defineStore } from 'pinia'

function savedUser(){
  try{return JSON.parse(localStorage.getItem('user'))||null}
  catch{return null}
}

export const useUserStore = defineStore('user', {
  state: () => ({
    user: savedUser(),
    token: localStorage.getItem('token') || null
  }),
  actions: {
    login(userData, userToken) {
      this.user = userData;
      this.token = userToken;
      localStorage.setItem('token', userToken);
      localStorage.setItem('user', JSON.stringify(userData));
    },
    logout() {
      this.user = null;
      this.token = null;
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  }
})
