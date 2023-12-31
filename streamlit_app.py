import streamlit as st
import tensorflow as tf

def generate(content_img, style_img, epc, itr):
    import os
    import tensorflow as tf
    # Load compressed models from tensorflow_hub
    os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
    import numpy as np 
    import PIL.Image
    import time

    imgs = st.empty()
    imgs.image(content_img)

    filepath = "styles/"+ style_img +"/"
    
    def tensor_to_image(tensor):
        tensor = tensor*255
        tensor = np.array(tensor, dtype=np.uint8)
        if np.ndim(tensor)>3:
            assert tensor.shape[0] == 1
            tensor = tensor[0]
        return PIL.Image.fromarray(tensor)

    def load_img(img):
        max_dim = 512
        img = img.read()
        img = tf.image.decode_image(img, channels=3)
        img = tf.image.convert_image_dtype(img, tf.float32)

        shape = tf.cast(tf.shape(img)[:-1], tf.float32)
        long_dim = max(shape)
        scale = max_dim / long_dim

        new_shape = tf.cast(shape * scale, tf.int32)

        img = tf.image.resize(img, new_shape)
        img = img[tf.newaxis, :]
        return img

    content_image = load_img(content_img)
    #style_image = load_img(style_img)


    x = tf.keras.applications.vgg19.preprocess_input(content_image*255)
    x = tf.image.resize(x, (224, 224))
    vgg = tf.keras.applications.VGG19(include_top=True, weights='imagenet')
    prediction_probabilities = vgg(x)

    predicted_top_5 = tf.keras.applications.vgg19.decode_predictions(prediction_probabilities.numpy())[0]

    vgg = tf.keras.applications.VGG19(include_top=False, weights='imagenet')

    content_layers = ['block5_conv2']

    style_layers = ['block1_conv1',
                'block2_conv1',
                'block3_conv1',
                'block4_conv1',
                'block5_conv1']

    num_content_layers = len(content_layers)
    num_style_layers = len(style_layers)

    def vgg_layers(layer_names):
        """ Creates a VGG model that returns a list of intermediate output values."""
        # Load our model. Load pretrained VGG, trained on ImageNet data
        vgg = tf.keras.applications.VGG19(include_top=False, weights='imagenet')
        vgg.trainable = False

        outputs = [vgg.get_layer(name).output for name in layer_names]

        model = tf.keras.Model([vgg.input], outputs)
        return model

    def gram_matrix(input_tensor):
        result = tf.linalg.einsum('bijc,bijd->bcd', input_tensor, input_tensor)
        input_shape = tf.shape(input_tensor)
        num_locations = tf.cast(input_shape[1]*input_shape[2], tf.float32)
        return result/(num_locations)

    class StyleContentModel(tf.keras.models.Model):
        def __init__(self, style_layers, content_layers):
            super(StyleContentModel, self).__init__()
            self.vgg = vgg_layers(style_layers + content_layers)
            self.style_layers = style_layers
            self.content_layers = content_layers
            self.num_style_layers = len(style_layers)
            self.vgg.trainable = False

        def call(self, inputs):
            "Expects float input in [0,1]"
            inputs = inputs*255.0
            preprocessed_input = tf.keras.applications.vgg19.preprocess_input(inputs)
            outputs = self.vgg(preprocessed_input)
            style_outputs, content_outputs = (outputs[:self.num_style_layers],
                                            outputs[self.num_style_layers:])

            style_outputs = [gram_matrix(style_output)
                            for style_output in style_outputs]

            content_dict = {content_name: value
                            for content_name, value
                            in zip(self.content_layers, content_outputs)}

            style_dict = {style_name: value
                        for style_name, value
                        in zip(self.style_layers, style_outputs)}

            return {'content': content_dict, 'style': style_dict}

    extractor = StyleContentModel(style_layers, content_layers)
    
    content_targets = extractor(content_image)['content']

    #style_targets = extractor(style_image)['style']


    #for name, tensor in style_targets.items():
    #    print(name)
    #    print(tensor)
    #    tf.saved_model.save(tf.Variable(tensor), 'styles/Monet/' + name)
    targets = []
    for layer in style_layers:
        target = tf.convert_to_tensor(tf.saved_model.load(filepath+layer))
        targets.append(target)
    

    style_targets = {style_name: value
                        for style_name, value
                        in zip(style_layers, targets)}

        
        

    #style_targets = tf.saved_model.load('styles/VanGogh')


    def clip_0_1(image):
        return tf.clip_by_value(image, clip_value_min=0.0, clip_value_max=1.0)

    opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

    style_weight=1e-2
    content_weight=1e4

    def style_content_loss(outputs):
        style_outputs = outputs['style']
        content_outputs = outputs['content']
        style_loss = tf.add_n([tf.reduce_mean((style_outputs[name]-style_targets[name])**2)
                                for name in style_outputs.keys()])
        style_loss *= style_weight / num_style_layers

        content_loss = tf.add_n([tf.reduce_mean((content_outputs[name]-content_targets[name])**2)
                                    for name in content_outputs.keys()])
        content_loss *= content_weight / num_content_layers
        loss = style_loss + content_loss
        return loss

    def high_pass_x_y(image):
        x_var = image[:, :, 1:, :] - image[:, :, :-1, :]
        y_var = image[:, 1:, :, :] - image[:, :-1, :, :]

        return x_var, y_var

    total_variation_weight=30

    @tf.function()
    def train_step(image):
        with tf.GradientTape() as tape:
            outputs = extractor(image)
            loss = style_content_loss(outputs)
            loss += total_variation_weight*tf.image.total_variation(image)

        grad = tape.gradient(loss, image)
        opt.apply_gradients([(grad, image)])
        image.assign(clip_0_1(image))

    opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)
    image = tf.Variable(content_image)

    import time
    start = time.time()

    step = 0
    
    for n in range(epc):
        for m in range(itr):
            step += 1
            train_step(image)
            print(".", end='', flush=True)
            imgs.image(tensor_to_image(image), caption=("Epoch " + str(n) + " - Iteration " + str(m)))

    end = time.time()
    imgs.empty()
    st.write("Total time: {:.1f}".format(end-start))
    return tensor_to_image(image)

with st.sidebar:
    st.title("Style Transfer")
    st.info("This application is originally developed from Tensorflow's Neural Style Transfer Tutorial")
    epc = st.slider('Number of epochs', 0, 10, 1)
    itr = st.slider('Number of iterations per epoch', 0, 100, 5)

col1, col2 = st.columns(2)

with col1:
    content_img = st.file_uploader("Choose a content image", type=['png', 'jpg', 'jpeg'])
    if content_img:
        st.image(content_img, caption='Content Image')
with col2:
    style_img = st.selectbox(
        'Choose a style to your image',
        ('VanGogh', 'DaVinci', 'Kadinsky', 'Munch', 'Monet'),
        index=None)

if content_img and style_img:
    btn = st.button('Generate!')
    if btn:
        out = st.empty()
        out.image(generate(content_img, style_img, epc, itr), caption="generated image")

