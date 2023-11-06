import streamlit as st

def generate():
    st.write("Hello")
    
with st.sidebar:
    st.title("Style Transfer")
    st.info("This application is originally developed from Tensorflow's Neural Style Transfer Tutorial")

col1, col2 = st.columns(2)

with col1:
    content_img = st.file_uploader("Choose a content image", type=['png', 'jpg', 'jpeg'])
    if content_img:
        st.image(content_img, caption='Content Image')
with col2:
    style_img = st.file_uploader("Choose a syle image", type=['png', 'jpg', 'jpeg'])
    if style_img:
        st.image(style_img, caption='Style Image')

st.button("Generate!", type="primary", disabled!=(content_img and style_img), on_click=generate())

