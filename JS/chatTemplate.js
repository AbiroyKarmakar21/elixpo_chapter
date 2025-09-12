let template = 
`
                   <section class="flex flex-col items-start mt-10 w-full h-auto ">
                    <div class="query font-bold text-[2em] text-white p-3 rounded-lg break-words">
                        <p>What are the latest advancements in renewable energy technologies in 2024?</p>
                    </div>
                    <div class="response text-lg text-white p-3 rounded-lg  break-words">
                        <div class="loader w-full h-[60px] flex flex-row gap-2 animation-rotate">
                            <ion-icon name="sparkles" class="text-[#888] text-[1.2em]"></ion-icon> 
                            <p class="SSEstatus text-m text-[#888]"> Thinking </p>
                        </div>

                        <div class="renderMarkdown w-full flex-col g-5" id="renderMarkdown">
                                <div class="renderMarkdownResult text-white break-words text-[1.2em]" id="renderMarkdownResult">
                                    
                                </div>


                                <div class="sources w-full mt-2">
                                    <div class="sourceHeading flex flex-row gap-5 mb-2 text-[#888] ">
                                        <ion-icon name="book-outline" class="text-[#888] text-[1.2em]"></ion-icon>
                                        <span>Sources</span>
                                    </div>
                                    <div class="sourceContainers flex flex-row gap-5 flex-wrap py-2 w-full">

                                            <div class="sourceItem h-[120px] w-[250px] bg-[#222] rounded-lg py-3 px-3 flex flex-col justify-between hover:bg-[#333] cursor-pointer overflow-hidden">
                                                <div class="firstRow flex flex-row w-[99%] items-center">
                                                    <div class="logoWebsite h-[20px] w-[20px] rounded-[8px] bg-cover bg-center mr-2"
                                                        style="background-image: url('https://www.google.com/s2/favicons?domain=elixpo.com&sz=32');"></div>
                                                    <span class="text-[#ccc] text-sm ml-2 truncate block max-w-[95%]" title="https://www.example.com/article1">https://www.example.com/article1</span>
                                                </div>
                                                <div class="secondRow text-[1em] text-[#fff] h-[60px] overflow-hidden mt-2">
                                                    Lorem, ipsum dolor sit amet consectetur adipisicing elit. Quasi expedita omnis mollitia provident voluptate aliquam consequuntur placeat cumque! Mollitia laboriosam aperiam commodi maxime veniam itaque voluptatum voluptates! Vel, deleniti autem!
                                                </div>
                                            </div>

                                            <div class="sourceItem h-[120px] w-[250px] bg-[#222] rounded-lg py-3 px-3 flex flex-col justify-between hover:bg-[#333] cursor-pointer overflow-hidden">
                                                <div class="firstRow flex flex-row w-[99%] items-center">
                                                    <div class="logoWebsite h-[20px] w-[20px] rounded-[8px] bg-cover bg-center mr-2"
                                                        style="background-image: url('https://www.google.com/s2/favicons?domain=elixpo.com&sz=32');"></div>
                                                    <span class="text-[#ccc] text-sm ml-2 truncate block max-w-[95%]" title="https://www.example.com/article1">https://www.example.com/article1</span>
                                                </div>
                                                <div class="secondRow text-[1em] text-[#fff] h-[60px] overflow-hidden mt-2">
                                                    Lorem, ipsum dolor sit amet consectetur adipisicing elit. Quasi expedita omnis mollitia provident voluptate aliquam consequuntur placeat cumque! Mollitia laboriosam aperiam commodi maxime veniam itaque voluptatum voluptates! Vel, deleniti autem!
                                                </div>
                                            </div>
                                            <div class="sourceItem h-[120px] w-[250px] bg-[#222] rounded-lg py-3 px-3 flex flex-col justify-between hover:bg-[#333] cursor-pointer overflow-hidden">
                                                <div class="firstRow flex flex-row w-[99%] items-center">
                                                    <div class="logoWebsite h-[20px] w-[20px] rounded-[8px] bg-cover bg-center mr-2"
                                                        style="background-image: url('https://www.google.com/s2/favicons?domain=elixpo.com&sz=32');"></div>
                                                    <span class="text-[#ccc] text-sm ml-2 truncate block max-w-[95%]" title="https://www.example.com/article1">https://www.example.com/article1</span>
                                                </div>
                                                <div class="secondRow text-[1em] text-[#fff] h-[60px] overflow-hidden mt-2">
                                                    Lorem, ipsum dolor sit amet consectetur adipisicing elit. Quasi expedita omnis mollitia provident voluptate aliquam consequuntur placeat cumque! Mollitia laboriosam aperiam commodi maxime veniam itaque voluptatum voluptates! Vel, deleniti autem!
                                                </div>
                                            </div>
                                    </div>
                                </div> 
                                
                                <div class="images w-full mt-2">
                                    <div class="imageHeading flex flex-row gap-5 mb-2 text-[#888] ">
                                        <ion-icon name="image-outline" class="text-[#888] text-[1.2em]"></ion-icon>
                                        <span>Images</span>
                                    </div>
                                    <div class="imageContainers flex flex-row gap-5 overflow-x-auto py-2 w-full">
                                        <img src="https://via.placeholder.com/150" alt="Image 1" class="h-[150px] w-[150px] rounded-lg bg-cover bg-center">
                                    </div>
                                </div>
                        </div>
                    </div>
                </section>

`