<template>
  <form @submit.prevent="onSubmit" data-test="signup-form">
    <input v-model="email" name="email" id="signup-email">
    <input v-model="password" type="password" name="password">
    <button v-on:click="track" type="submit">Go</button>
    <router-link to="/login">Log in</router-link>
    <slot name="footer"></slot>
  </form>
</template>

<script setup lang="ts">
import { ref } from "vue";
const email = ref<string>("");
function onSubmit() {}
</script>
